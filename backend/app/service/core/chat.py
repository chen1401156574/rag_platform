from openai import OpenAI
import os
import json
import redis
import re
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from utils.database import get_db
from fastapi import HTTPException
from service.settings_service import get_chat_model, get_generation_temperature, get_prompt_template
from utils import logger
from dotenv import load_dotenv

load_dotenv()


def _summary_text(text: str, limit: int = 600) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"...(已截断，原长度 {len(text)})"


def _citation_count(text: str) -> int:
    return len(re.findall(r"##\d+\$\$", text or ""))


def render_prompt_template(template: str, question: str, formatted_references: str) -> str:
    has_references = "{references}" in template or "{formatted_references}" in template
    has_question = "{question}" in template
    prompt = (
        template.replace("{formatted_references}", formatted_references)
        .replace("{references}", formatted_references)
        .replace("{question}", question)
    )
    if not has_references:
        prompt = f"{prompt}\n\n参考内容：\n{formatted_references}"
    if not has_question:
        prompt = f"{prompt}\n\n用户问题：\n{question}"
    return prompt

# Redis 客户端初始化
def get_redis_client():
    """获取 Redis 客户端"""
    redis_host = os.getenv('REDIS_HOST', 'redis')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_db = int(os.getenv('REDIS_DB', 0))
    return redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)

def get_quick_parse_content(session_id: str) -> str:
    """从 Redis 获取快速解析的文档内容"""
    try:
        redis_client = get_redis_client()
        content = redis_client.get(session_id)
        if content:
            logger.info(f"从 Redis 获取到快速解析内容，session_id: {session_id}, 长度: {len(content)}")
            return content
        else:
            logger.info(f"Redis 中未找到快速解析内容，session_id: {session_id}")
            return None
    except Exception as e:
        logger.error(f"从 Redis 获取快速解析内容失败: {str(e)}")
        return None

def generate_recommended_questions(user_question, retrieved_content=None, session_id=None):
    """
    根据用户提问生成相关推荐问题。

    :param user_question: 用户提问
    :param retrieved_content: 检索到的内容（可选，用于判断是否有相关文档）
    :param session_id: 会话ID（可选）
    :return: 推荐问题列表
    """
    # 判断是否有文档上下文
    has_documents = bool(retrieved_content and len(retrieved_content) > 0)
    
    # 获取文档主题信息（简化版）
    document_topics = []
    if has_documents:
        # 只获取文档名称作为主题参考，避免内容过长
        document_names = list(set([ref.get('document_name', '') for ref in retrieved_content if ref.get('document_name')]))
        document_topics = document_names[:3]  # 最多3个文档名称

   # 构造优化后的提示词
    context_info = ""
    if has_documents and document_topics:
        context_info = f"当前对话基于这些文档：{', '.join(document_topics)}"
    
    prompt = f"""
你是一个智能助手，请基于用户的问题生成3个相关的推荐问题，帮助用户更深入地探索这个话题。

用户问题：{user_question}
{context_info}

要求：
1. 生成的问题应该与用户问题相关，但从不同角度深入
2. 问题要具体、有价值，能够引导用户获得更多有用信息
3. 如果有文档上下文，可以围绕文档主题生成相关问题
4. 返回JSON格式，包含recommended_questions数组

输出格式：
{{
  "recommended_questions": [
    "具体问题1",
    "具体问题2", 
    "具体问题3"
  ]
}}

请直接返回JSON，不要包含其他文字。
    """
    
    try:
        # 调用大模型生成推荐问题
        client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url=os.getenv("DASHSCOPE_BASE_URL")
            )
        completion = client.chat.completions.create(
            model="qwen2.5-7b-instruct",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            stream=False,
            timeout=30,  # 添加超时设置
        )

        # 提取生成的推荐问题
        if completion.choices:
            response = completion.choices[0].message.content
            logger.info(f"大模型返回的推荐问题原始响应: {response}")
            
            try:
                # 清理响应内容，去掉可能的markdown代码块标识符
                import re
                cleaned_response = response.strip()
                
                # 使用正则表达式去掉```json开头和```结尾
                json_pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
                match = re.search(json_pattern, cleaned_response, re.DOTALL | re.IGNORECASE)
                
                if match:
                    cleaned_response = match.group(1).strip()
                    logger.info(f"检测到markdown代码块，已清理")
                
                logger.info(f"清理后的响应内容: {cleaned_response}")
                
                # 解析 JSON 响应
                response_json = json.loads(cleaned_response)
                recommended_questions = response_json.get("recommended_questions", [])
                logger.info(f"解析后的推荐问题: {recommended_questions}")
                
                # 验证推荐问题格式
                if isinstance(recommended_questions, list) and len(recommended_questions) > 0:
                    return recommended_questions
                else:
                    logger.warning("推荐问题格式不正确或为空")
                    return []
                    
            except json.JSONDecodeError as e:
                logger.error(f"解析推荐问题JSON失败: {str(e)}")
                logger.error(f"原始响应内容: {response}")
                logger.error(f"清理后内容: {cleaned_response if 'cleaned_response' in locals() else '未处理'}")
                return []
        else:
            logger.warning("大模型没有返回任何选择")
            return []
            
    except Exception as e:
        logger.error(f"调用大模型生成推荐问题时发生错误: {str(e)}")
        return []

def generate_session_name(user_question):
    prompt = f"""
    请根据以下用户提问，生成一个简洁且具有代表性的会话名称：
    用户提问：{user_question}

    要求：
    1. 会话名称应简洁明了，能够概括用户提问的主题。
    2. 返回一个 JSON 对象，包含一个字段 "session_name"，值为生成的会话名称。

    输出格式示例：
    {{
      "session_name": "会话名称内容"
    }}

    请严格按照上述格式返回 JSON 对象。
    """
    
    # 调用大模型生成会话名称
    try:
        client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url=os.getenv("DASHSCOPE_BASE_URL")
            )
        completion = client.chat.completions.create(
            model="qwen2.5-72b-instruct",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            stream=False,
        )

        # 提取生成的会话名称
        if completion.choices:
            response = completion.choices[0].message.content
            try:
                # 解析 JSON 响应
                response_json = json.loads(response)
                session_name = response_json.get("session_name")
                print("生成的会话名称：\n")
                print(session_name)
                return session_name
            except json.JSONDecodeError:
                print("Failed to parse JSON response.")
                return user_question
    except Exception as e:
        print(f"An error occurred: {e}")
        return user_question


def write_chat_to_db(session_id: str, user_question: str, model_answer: str, retrieval_content, recommended_questions, think ):
    """
    将对话数据写入数据库。

    :param session_id: 会话 ID
    :param user_question: 用户问题
    :param model_answer: 大模型的回答
    :param retrieval_content: 检索内容
    """
    db = next(get_db())  # 获取数据库会话
    try:
        documents_json = json.dumps(retrieval_content, ensure_ascii=False)

        db.execute(
            text(
                """
                INSERT INTO messages (session_id, user_question, model_answer, documents, recommended_questions, think )
                VALUES (:session_id, :user_question, :model_answer, :documents, :recommended_questions, :think)
                """
            ),
            {
                "session_id": session_id,
                "user_question": user_question,
                "model_answer": model_answer,
                "documents": documents_json,
                "recommended_questions": recommended_questions,
                "think": think,
            }
        )
        db.commit()
        logger.info("对话数据插入成功。。。")
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write to database: {str(e)}"
        )
    finally:
        db.close()

def update_session_name(session_id: str, question: str, user_id: str):
    """
    根据 session_id 查数据库的表 sessions，有的话直接跳过，没有的话先生成 session_name，再插入。

    :param session_id: 会话 ID
    :param user_id: 用户 ID
    """
    db = next(get_db())  # 获取数据库会话
    try:
        # 查询 sessions 表中是否存在该 session_id
        query_result = db.execute(
            text("SELECT session_name FROM sessions WHERE session_id = :session_id"),
            {"session_id": session_id}
        ).fetchone()

        if query_result:
            # 如果查到了，直接跳过
            logger.info(f"Session {session_id} already exists, skipping.")
        else:
            if question:
                session_name = generate_session_name(question)
                db.execute(
                    text(
                        """
                        INSERT INTO sessions (session_id, user_id, session_name)
                        VALUES (:session_id, :user_id, :session_name)
                        """
                    ),
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "session_name": session_name
                    }
                )
                db.commit()
                logger.info("会话数据插入成功。。。")
                print(f"New session {session_id} inserted with name: {session_name}")
            else:
                print(f"Failed to retrieve question for session {session_id}, skipping insertion.")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database operation failed: {str(e)}"
        )
    finally:
        db.close()

def get_chat_completion(session_id, question, retrieved_content, user_id, tracker=None, settings=None):
    """
    获取流式聊天完成结果，并按照指定格式输出。

    :param session_id: 会话 ID（可选，如需区分不同会话可传入）
    :param question: 用户问题
    :param retrieved_content: 从知识库检索的内容
    :param user_id: 用户ID
    :param tracker: 链路追踪器 Tracker
    :param settings: 系统设置快照
    :return: 流式输出的生成器，每个元素为符合 SSE 格式的字符串
    """
    quick_start = datetime.now()
    quick_parse_content = get_quick_parse_content(session_id)
    quick_end = datetime.now()
    if tracker:
        tracker.record_node(
            node_type="QuickParseLoad",
            node_name="Quick Parse Load",
            start_time=quick_start,
            end_time=quick_end,
            status="success",
            input_data={"session_id": session_id},
            output_data={
                "hit": bool(quick_parse_content),
                "content_length": len(quick_parse_content or ""),
            },
        )

    reference_parts = []
    reference_id = 1
    knowledge_reference_count = 0
    quick_reference_count = 0

    if retrieved_content:
        knowledge_base_refs = []
        for ref in retrieved_content:
            knowledge_base_refs.append(f"##{reference_id}$$ {ref['content_with_weight']}")
            reference_id += 1
            knowledge_reference_count += 1
        if knowledge_base_refs:
            reference_parts.append("**知识库内容：**\n" + "\n".join(knowledge_base_refs))

    if quick_parse_content:
        quick_content_paragraphs = [para.strip() for para in quick_parse_content.split('\n') if para.strip()]
        if quick_content_paragraphs:
            max_quick_content_length = 4000
            truncated_content = quick_parse_content[:max_quick_content_length]
            if len(quick_parse_content) > max_quick_content_length:
                truncated_content += "...(内容已截断)"
            reference_parts.append(f"**当前会话文档内容：**\n##{reference_id}$$ {truncated_content}")
            reference_id += 1
            quick_reference_count = 1

    formatted_references = "\n\n".join(reference_parts) if reference_parts else "暂无相关参考内容"
    if tracker:
        tracker.record_event(
            node_type="ContextAssemble",
            node_name="Context Assemble",
            input_data={
                "question": question,
                "retrieved_count": len(retrieved_content or []),
                "quick_parse_hit": bool(quick_parse_content),
            },
            output_data={
                "knowledge_reference_count": knowledge_reference_count,
                "quick_reference_count": quick_reference_count,
                "total_reference_count": knowledge_reference_count + quick_reference_count,
                "formatted_reference_length": len(formatted_references),
            },
        )

    prompt_template = get_prompt_template(settings or {})
    prompt = render_prompt_template(prompt_template, question, formatted_references)
    if tracker:
        tracker.record_event(
            node_type="PromptBuild",
            node_name="Prompt Build",
            input_data={
                "question": question,
                "template_has_references": "{references}" in prompt_template or "{formatted_references}" in prompt_template,
                "template_has_question": "{question}" in prompt_template,
            },
            output_data={
                "prompt_length": len(prompt),
                "prompt_summary": _summary_text(prompt, 1200),
                "reference_range": f"1-{max(reference_id - 1, 0)}" if reference_id > 1 else "none",
            },
        )

    print(prompt)

    llm_start_time = datetime.now()
    ttft_recorded = False
    ttft_time = None
    model_answer = ""
    think = ""
    recommended_questions = []
    stream_chunk_count = 0
    answer_chunk_count = 0
    thinking_chunk_count = 0
    model_name = get_chat_model(settings or {})
    temperature = get_generation_temperature(settings or {})

    try:
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL")
        )

        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            temperature=temperature,
        )
        llm_request_end = datetime.now()
        if tracker:
            tracker.record_node(
                node_type="LLMStreamStart",
                node_name="LLM Stream Start",
                start_time=llm_start_time,
                end_time=llm_request_end,
                status="success",
                input_data={"model": model_name, "temperature": temperature, "stream": True},
                output_data={"provider": "dashscope-openai-compatible"},
            )

        all_documents = retrieved_content.copy() if retrieved_content else []
        quick_content_chunks = []
        if quick_parse_content:
            max_chunk_length = 2000
            if len(quick_parse_content) <= max_chunk_length:
                quick_content_chunks = [quick_parse_content]
            else:
                paragraphs = [p.strip() for p in quick_parse_content.split('\n') if p.strip()]
                current_chunk = ""
                for paragraph in paragraphs:
                    if len(current_chunk + paragraph) <= max_chunk_length:
                        current_chunk += paragraph + "\n"
                    else:
                        if current_chunk:
                            quick_content_chunks.append(current_chunk.strip())
                        current_chunk = paragraph + "\n"
                if current_chunk:
                    quick_content_chunks.append(current_chunk.strip())

            for i, chunk_text in enumerate(quick_content_chunks):
                quick_parse_doc = {
                    "document_id": f"quick_parse_{session_id}_{i}",
                    "document_name": f"当前会话文档-第{i+1}部分" if len(quick_content_chunks) > 1 else "当前会话文档",
                    "content_with_weight": chunk_text,
                    "id": f"quick_parse_{session_id}_{i}",
                    "positions": []
                }
                all_documents.append(quick_parse_doc)

            logger.info(f"快速解析内容已添加到文档列表，共{len(quick_content_chunks)}个部分")

        message = {"documents": all_documents}
        json_message = json.dumps(message, ensure_ascii=False)
        if tracker:
            tracker.record_event(
                node_type="SSEDocumentsSent",
                node_name="SSE Documents Sent",
                output_data={
                    "document_count": len(all_documents),
                    "knowledge_document_count": len(retrieved_content or []),
                    "quick_parse_document_count": len(quick_content_chunks),
                },
            )
        yield f"event: message\ndata: {json_message}\n\n"

        for chunk in completion:
            stream_chunk_count += 1
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            if not ttft_recorded and delta:
                first_content = getattr(delta, "content", None)
                first_reasoning = getattr(delta, "reasoning_content", None)
                if first_content or first_reasoning:
                    ttft_time = datetime.now()
                    ttft_recorded = True
                    if tracker:
                        tracker.record_node(
                            node_type="LLMFirstToken",
                            node_name="LLM First Token",
                            start_time=llm_start_time,
                            end_time=ttft_time,
                            status="success",
                            output_data={
                                "ttft_ms": int((ttft_time - llm_start_time).total_seconds() * 1000),
                                "first_token_type": "content" if first_content else "reasoning_content",
                            },
                        )

            if choice.finish_reason == "stop":
                llm_end_time = datetime.now()
                ttft_ms = int((ttft_time - llm_start_time).total_seconds() * 1000) if ttft_time else 0
                if tracker:
                    tracker.record_node(
                        node_type="LLMAnswerStream",
                        node_name="LLM Answer Stream",
                        start_time=llm_start_time,
                        end_time=llm_end_time,
                        status="success",
                        output_data={
                            "stream_chunk_count": stream_chunk_count,
                            "answer_chunk_count": answer_chunk_count,
                            "thinking_chunk_count": thinking_chunk_count,
                            "answer_chars": len(model_answer),
                            "thinking_chars": len(think),
                        },
                    )

                recommend_start = datetime.now()
                try:
                    logger.info("开始生成推荐问题...")
                    recommended_questions = generate_recommended_questions(question, retrieved_content, session_id)
                    logger.info(f"推荐问题生成结果: {recommended_questions}")
                    recommend_end = datetime.now()
                    if tracker:
                        tracker.record_node(
                            node_type="RecommendQuestions",
                            node_name="Recommend Questions",
                            start_time=recommend_start,
                            end_time=recommend_end,
                            status="success",
                            input_data={"question": question, "document_count": len(retrieved_content or [])},
                            output_data={
                                "recommended_questions": recommended_questions,
                                "recommended_question_count": len(recommended_questions or []),
                            },
                        )

                    if recommended_questions:
                        message = {"recommended_questions": recommended_questions}
                        json_message = json.dumps(message, ensure_ascii=False)
                        yield f"event: message\ndata: {json_message}\n\n"
                        logger.info("推荐问题已发送给前端")
                    else:
                        logger.warning("推荐问题生成为空")
                except Exception as e:
                    recommend_end = datetime.now()
                    logger.error(f"生成推荐问题失败: {str(e)}")
                    recommended_questions = []
                    if tracker:
                        tracker.record_node(
                            node_type="RecommendQuestions",
                            node_name="Recommend Questions",
                            start_time=recommend_start,
                            end_time=recommend_end,
                            status="failed",
                            error_message=str(e),
                            input_data={"question": question},
                        )

                if tracker:
                    final_answer_data = {
                        "answer_summary": _summary_text(model_answer, 1200),
                        "answer_chars": len(model_answer),
                        "thinking_chars": len(think),
                        "citation_marker_count": _citation_count(model_answer),
                        "finish_reason": "stop",
                    }
                    tracker.record_event(
                        node_type="LLMFinalAnswer",
                        node_name="LLM Final Answer",
                        output_data=final_answer_data,
                    )
                    tracker.record_node(
                        node_type="LLMCall",
                        node_name="Large Language Model Call",
                        start_time=llm_start_time,
                        end_time=llm_end_time,
                        status="success",
                        input_data={"prompt": _summary_text(prompt, 1500), "model": model_name},
                        output_data={"answer": _summary_text(model_answer, 1500), "thinking": _summary_text(think, 1500)},
                        extra_data={"recommended_questions": recommended_questions}
                    )
                    tracker.record_event(
                        node_type="SSEEndSent",
                        node_name="SSE End Sent",
                        output_data={"data": "[DONE]", "end_type": "success"},
                    )

                yield "event: end\ndata: [DONE]\n\n"

                print("最终回答：\n")
                print(model_answer)

                persist_ok = True
                persist_error = None
                persist_start = datetime.now()
                try:
                    write_chat_to_db(session_id, question, model_answer, all_documents, recommended_questions, think)
                    persist_end = datetime.now()
                    if tracker:
                        tracker.record_node(
                            node_type="PersistMessage",
                            node_name="Persist Message",
                            start_time=persist_start,
                            end_time=persist_end,
                            status="success",
                            input_data={"session_id": session_id, "question": question},
                            output_data={
                                "documents_count": len(all_documents),
                                "recommended_question_count": len(recommended_questions or []),
                                "answer_chars": len(model_answer),
                                "thinking_chars": len(think),
                            },
                        )
                except Exception as e:
                    persist_ok = False
                    persist_error = str(e)
                    persist_end = datetime.now()
                    logger.error(f"对话数据落库失败: {persist_error}")
                    if tracker:
                        tracker.record_node(
                            node_type="PersistMessage",
                            node_name="Persist Message",
                            start_time=persist_start,
                            end_time=persist_end,
                            status="failed",
                            error_message=persist_error,
                            input_data={"session_id": session_id, "question": question},
                        )

                title_start = datetime.now()
                try:
                    update_session_name(session_id, question, user_id)
                    title_end = datetime.now()
                    if tracker:
                        tracker.record_node(
                            node_type="SessionTitleUpdate",
                            node_name="Session Title Update",
                            start_time=title_start,
                            end_time=title_end,
                            status="success",
                            input_data={"session_id": session_id, "user_id": user_id},
                            output_data={"attempted": True},
                        )
                except Exception as e:
                    title_end = datetime.now()
                    logger.error(f"会话标题更新失败: {str(e)}")
                    if tracker:
                        tracker.record_node(
                            node_type="SessionTitleUpdate",
                            node_name="Session Title Update",
                            start_time=title_start,
                            end_time=title_end,
                            status="failed",
                            error_message=str(e),
                            input_data={"session_id": session_id, "user_id": user_id},
                        )

                if tracker:
                    if persist_ok:
                        tracker.finish_run(status="success", ttft_ms=ttft_ms)
                    else:
                        tracker.finish_run(
                            status="failed",
                            ttft_ms=ttft_ms,
                            error_message=f"回答已返回但落库失败: {persist_error}",
                        )
                break

            content = getattr(delta, "content", None) if delta else None
            reasoning_content = getattr(delta, "reasoning_content", None) if delta else None
            if content:
                answer_chunk_count += 1
                model_answer += content
                message = {
                    "role": "assistant",
                    "content": content,
                    "thinking": False,
                }
                json_message = json.dumps(message, ensure_ascii=False)
                yield f"event: message\ndata: {json_message}\n\n"
            elif reasoning_content:
                thinking_chunk_count += 1
                think += reasoning_content
                message = {
                    "role": "assistant",
                    "content": reasoning_content,
                    "thinking": True,
                }
                json_message = json.dumps(message, ensure_ascii=False)
                yield f"event: message\ndata: {json_message}\n\n"

    except Exception as e:
        llm_end_time = datetime.now()
        if tracker:
            tracker.record_node(
                node_type="LLMCall",
                node_name="Large Language Model Call",
                start_time=llm_start_time,
                end_time=llm_end_time,
                status="failed",
                error_message=str(e),
                input_data={"model": model_name, "prompt": _summary_text(prompt, 1500)},
                output_data={"partial_answer": _summary_text(model_answer, 1000), "partial_thinking": _summary_text(think, 1000)},
            )
            tracker.record_event(
                node_type="SSEErrorSent",
                node_name="SSE Error Sent",
                status="failed",
                output_data={"role": "error", "content": str(e)},
            )
            tracker.finish_run(status="failed", error_message=str(e))

        error_message = {
            "role": "error",
            "content": str(e)
        }
        json_error_message = json.dumps(error_message, ensure_ascii=False)
        yield f"event: error\ndata: {json_error_message}\n\n"


def stream_clarify_response(question: str, clarifying_questions: list[str]):
    """生成追问事件的 SSE 流，前端收到后展示追问问题"""
    message = {
        "clarifying_questions": clarifying_questions,
        "original_question": question,
    }
    json_message = json.dumps(message, ensure_ascii=False)
    yield f"event: clarify\ndata: {json_message}\n\n"
    yield f"event: end\ndata: [DONE]\n\n"
