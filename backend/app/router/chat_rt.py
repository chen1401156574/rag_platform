from fastapi import APIRouter, Body, UploadFile, File, HTTPException, Query, Security, status, Depends
import copy
import uuid
from schemas.chat import SessionResponse, ChatRequest
from fastapi.responses import StreamingResponse
import os
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Optional
from service.core.file_parse import execute_insert_process
from service.core.api.utils.file_utils import get_project_base_directory
from fastapi_jwt import JwtAuthorizationCredentials
from service.core.retrieval import retrieve_content
from service.core.chat import get_chat_completion, stream_clarify_response
from service.ambiguity_service import check_draft_and_clarify, merge_clarifications
from service.intent_engine import default_intent_router
from service.auth import access_security
from service.settings_service import get_retrieval_top_k, load_settings
from service.trace_service import TraceTracker
from utils import logger
from database.knowledgebase_operations import insert_knowledgebase, verify_user_knowledgebase
from sqlalchemy.orm import Session
from sqlalchemy import select
from models.message import KnowledgeBase
from utils.database import get_db
from service.quick_parse_service import quick_parse_service
from service.document_upload_service import DocumentUploadService
from schemas.document_upload import DocumentUploadResponse, SessionDocumentsResponse, SessionDocumentSummary
import os

# 加载 .env 文件
load_dotenv()

# 配置日志
logger.info(f"ES_HOST: {os.getenv('ES_HOST')}")
logger.info(f"ELASTICSEARCH_URL: {os.getenv('ELASTICSEARCH_URL')}")

router = APIRouter()
intent_router = default_intent_router()


def _get_chat_user(credentials: JwtAuthorizationCredentials) -> tuple[str, str]:
    subject = credentials.subject or {}
    user_id = subject.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return str(user_id), subject.get("user_name", "user")


def _stream_chat_response(
    *,
    session_id: str,
    question: str,
    user_id: str,
    user_name: str,
    db: Session,
    trace_name: str,
    entry_method: str,
    deep_thinking: bool = False,
    clarifications: Optional[str] = None,
    original_question: Optional[str] = None,
):
    tracker = TraceTracker(db)
    tracker.start_run(
        question=question,
        conversation_id=session_id,
        user_id=user_id,
        user_name=user_name,
        trace_name=trace_name,
        entry_method=entry_method,
    )
    tracker.record_event(
        node_type="UserQuestionReceived",
        node_name="User Question Received",
        input_data={
            "session_id": session_id,
            "entry_method": entry_method,
            "question": question,
            "has_clarifications": bool(clarifications and original_question),
        },
        output_data={"trace_id": tracker.trace_id},
    )

    logger.info(
        f"Start chat request: user_id={user_id}, session_id={session_id}, entry_method={entry_method}"
    )
    logger.info(f"Question: {question}")
    settings_start = datetime.now()
    settings = load_settings(db)
    if deep_thinking:
        deep_model = settings.get("ai", {}).get("chat", {}).get("deepThinkingModel")
        if deep_model:
            settings = copy.deepcopy(settings)
            settings.setdefault("ai", {}).setdefault("chat", {})["defaultModel"] = deep_model
    top_k = get_retrieval_top_k(settings)
    settings_end = datetime.now()
    tracker.record_node(
        node_type="AuthLoadSettings",
        node_name="Auth And Settings",
        start_time=settings_start,
        end_time=settings_end,
        status="success",
        input_data={"user_id": user_id, "session_id": session_id, "deep_thinking": deep_thinking},
        output_data={
            "top_k": top_k,
            "default_model": settings.get("ai", {}).get("chat", {}).get("defaultModel"),
            "deep_thinking_model": settings.get("ai", {}).get("chat", {}).get("deepThinkingModel"),
            "temperature": settings.get("rag", {}).get("generation", {}).get("temperature"),
        },
    )

    intent_start = datetime.now()
    decision = intent_router.decide(db, question, user_id)
    intent_end = datetime.now()

    intent_output = {}
    if decision.intent:
        intent_output = {
            "intent_code": decision.intent.intent_code,
            "name": decision.intent.name,
            "kind": decision.intent.kind,
            "score": decision.score,
        }
    tracker.record_node(
        node_type="IntentClassify",
        node_name="Intent Classification",
        start_time=intent_start,
        end_time=intent_end,
        status="success",
        input_data={"question": question},
        output_data=intent_output,
    )

    if decision.intent:
        logger.info(
            f"Intent classified: code={decision.intent.intent_code}, "
            f"stored_kind={decision.intent.kind}, score={decision.score}"
        )
    else:
        logger.info("No reliable intent matched; using default retrieval route")

    references = []
    retrieval_start = datetime.now()
    try:
        logger.info("Start retrieving related content")
        references = retrieve_content(
            user_id,
            question,
            top_k=top_k,
            kb_ids=None,
            tracker=tracker,
        )
        logger.info(f"Retrieved {len(references)} related references")
        retrieval_end = datetime.now()

        tracker.record_node(
            node_type="VectorRetrieve",
            node_name="Vector Retrieval",
            start_time=retrieval_start,
            end_time=retrieval_end,
            status="success",
            input_data={"question": question, "top_k": top_k},
            output_data={"references_count": len(references), "references": references},
        )
    except Exception as e:
        logger.info(f"Retrieval failed or no knowledge base is available: {str(e)}")
        references = []
        retrieval_end = datetime.now()
        tracker.record_node(
            node_type="VectorRetrieve",
            node_name="Vector Retrieval",
            start_time=retrieval_start,
            end_time=retrieval_end,
            status="failed",
            error_message=str(e),
            input_data={"question": question, "top_k": top_k},
        )

    # 处理追问澄清：若用户已回答追问，合并后重新检索
    effective_question = question
    if clarifications and original_question:
        merge_start = datetime.now()
        effective_question = merge_clarifications(original_question, clarifications)
        merge_end = datetime.now()
        tracker.record_node(
            node_type="ClarificationMerge",
            node_name="Clarification Merge",
            start_time=merge_start,
            end_time=merge_end,
            status="success",
            input_data={
                "original_question": original_question,
                "clarifications": clarifications,
            },
            output_data={"effective_question": effective_question},
        )
        logger.info(f"追问澄清合并完成，原始提问: {original_question}")
        logger.info(f"补充说明: {clarifications}")
        # 用合并后的问题重新检索
        clarify_retrieval_start = datetime.now()
        try:
            logger.info("使用合并后的问题重新检索")
            references = retrieve_content(
                user_id,
                effective_question,
                top_k=top_k,
                kb_ids=None,
                tracker=tracker,
            )
            logger.info(f"重新检索获得 {len(references)} 条参考内容")
            clarify_retrieval_end = datetime.now()
            tracker.record_node(
                node_type="VectorRetrieve",
                node_name="Vector Retrieval After Clarification",
                start_time=clarify_retrieval_start,
                end_time=clarify_retrieval_end,
                status="success",
                input_data={"question": effective_question, "top_k": top_k, "source": "clarification_merge"},
                output_data={"references_count": len(references), "references": references},
                node_id="VectorRetrieveClarified",
            )
        except Exception as e:
            logger.warning(f"重新检索失败: {str(e)}")
            clarify_retrieval_end = datetime.now()
            tracker.record_node(
                node_type="VectorRetrieve",
                node_name="Vector Retrieval After Clarification",
                start_time=clarify_retrieval_start,
                end_time=clarify_retrieval_end,
                status="failed",
                error_message=str(e),
                input_data={"question": effective_question, "top_k": top_k, "source": "clarification_merge"},
                node_id="VectorRetrieveClarified",
            )

    # 歧义检测：生成草稿回答并自查不确定性
    if not clarifications and references:
        ambiguity_start = datetime.now()
        clarifying_questions = check_draft_and_clarify(question, references, settings)
        ambiguity_end = datetime.now()
        tracker.record_node(
            node_type="AmbiguityAudit",
            node_name="Ambiguity Audit",
            start_time=ambiguity_start,
            end_time=ambiguity_end,
            status="success",
            input_data={"question": question, "references_count": len(references)},
            output_data={
                "need_clarify": bool(clarifying_questions),
                "clarifying_questions": clarifying_questions or [],
                "clarifying_question_count": len(clarifying_questions or []),
            },
        )
        if clarifying_questions:
            logger.info(f"检测到歧义，生成 {len(clarifying_questions)} 个追问")
            tracker.record_event(
                node_type="ClarifyResponse",
                node_name="Clarify SSE Response",
                output_data={
                    "original_question": question,
                    "clarifying_questions": clarifying_questions,
                    "will_send_end": True,
                },
            )
            tracker.record_event(
                node_type="SSEEndSent",
                node_name="SSE End Sent",
                output_data={"data": "[DONE]", "end_type": "clarify_needed"},
            )
            tracker.finish_run(status="clarify_needed")
            return StreamingResponse(
                stream_clarify_response(question, clarifying_questions),
                media_type="text/event-stream",
            )
    elif clarifications:
        tracker.record_event(
            node_type="AmbiguityAudit",
            node_name="Ambiguity Audit Skipped",
            status="skipped",
            input_data={"reason": "clarification_answer_turn"},
            output_data={"effective_question": effective_question},
        )
    else:
        tracker.record_event(
            node_type="AmbiguityAudit",
            node_name="Ambiguity Audit Skipped",
            status="skipped",
            input_data={"reason": "no_references"},
        )

    logger.info("Start generating answer")
    return StreamingResponse(
        get_chat_completion(session_id, effective_question, references, user_id, tracker=tracker, settings=settings),
        media_type="text/event-stream",
    )

##################################
# 创建一个新的对话 Session
##################################

@router.post("/create_session", response_model=SessionResponse)
async def create_session(
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        user_id = credentials.subject.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        session_id = str(uuid.uuid4()).replace("-", "")[:16]

        return {
            "session_id": session_id,
            "status": "success",
            "message": "Session created successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

##################################
# 快速文档解析接口
##################################

@router.post("/quick_parse")
async def quick_parse_document(
    session_id: str = Query(..., description="会话ID"),
    file: UploadFile = File(..., description="要解析的文档"),
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    """
    快速文档解析接口
    - 支持文档格式：docx, pdf, txt
    - 限制文档页数不超过4页
    - 每个session_id只能传递一个文档
    - 解析结果存储到Redis，保存时间为2小时
    """
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 读取文件内容
        file_content = await file.read()
        
        # 获取文件信息
        file_size = len(file_content)
        file_extension = os.path.splitext(file.filename)[1].lower() if file.filename else ""
        document_type = file_extension.replace(".", "") if file_extension else "unknown"
        
        # 调用服务层处理业务逻辑
        result = quick_parse_service.quick_parse_document(
            session_id=session_id,
            filename=file.filename,
            file_content=file_content
        )
        
        # 记录文档上传信息到数据库
        try:
            DocumentUploadService.create_upload_record(
                db=db,
                session_id=session_id,
                document_name=file.filename,
                document_type=document_type,
                file_size=file_size
            )
            logger.info(f"文档上传记录已保存: session_id={session_id}, document_name={file.filename}")
        except Exception as db_error:
            logger.error(f"保存文档上传记录失败: {str(db_error)}")
            # 数据库记录失败不影响主要功能，继续返回解析结果
        
        logger.info(f"用户 {user_id} 的文档解析完成，session_id: {session_id}")
        return result

    except HTTPException as e:
        logger.error(f"快速解析错误: {str(e)}")
        raise e
    except Exception as e:
        logger.exception(f"快速解析发生未知错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务器错误: {str(e)}"
        )

##################################
# 获取解析内容接口
##################################

@router.get("/get_parsed_content")
async def get_parsed_content(
    session_id: str = Query(..., description="会话ID"),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    """
    获取已解析的文档内容
    """
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 调用服务层获取内容
        result = quick_parse_service.get_parsed_content(session_id)
        
        logger.info(f"用户 {user_id} 获取解析内容，session_id: {session_id}")
        return result

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

##################################
# 基于ragflow知识库对话
##################################

@router.post("/chat_on_docs")
async def chat_on_docs(
    session_id: str = Query(...),
    request: ChatRequest = Body(..., description="User message"),
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    try:
        user_id, user_name = _get_chat_user(credentials)
        return _stream_chat_response(
            session_id=session_id,
            question=request.message,
            user_id=user_id,
            user_name=user_name,
            db=db,
            trace_name="Chat on Docs",
            entry_method="chat_on_docs",
            clarifications=request.clarifications,
            original_question=request.original_question,
        )
    except HTTPException as e:
        logger.error(f"HTTP error: {str(e)}")
        raise e
    except Exception as e:
        logger.exception(f"Unknown chat error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/rag/v3/chat")
async def ragent_chat_compat(
    question: str = Query(..., description="User message"),
    conversationId: Optional[str] = Query(None, description="Session ID"),
    deepThinking: Optional[bool] = Query(False, description="Use deep thinking"),
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    try:
        user_id, user_name = _get_chat_user(credentials)
        session_id = conversationId or str(uuid.uuid4()).replace("-", "")[:16]
        if deepThinking:
            logger.info("deepThinking is accepted for compatibility and handled by the shared chat chain")
        return _stream_chat_response(
            session_id=session_id,
            question=question,
            user_id=user_id,
            user_name=user_name,
            db=db,
            trace_name="Ragent Chat Compat",
            entry_method="ragent_chat_compat",
            deep_thinking=bool(deepThinking),
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"Unknown chat error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/upload_files")
async def upload_files(
    session_id: Optional[str] = Query(None),
    files: List[UploadFile] = File(...),
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 如果没有 session_id，使用 user_id 作为 session_id
        if session_id is None:
            session_id = user_id

        # 确保 storage/file 文件夹存在
        storage_dir = os.path.join(get_project_base_directory(), "storage/file")
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
        
        # 根据 session_id 创建子文件夹
        session_dir = os.path.join(storage_dir, session_id)
        if not os.path.exists(session_dir):
            os.makedirs(session_dir)
        
        # 检查文件名是否重复
        existing_files = []
        for file in files:
            file_name = file.filename
            # 查询数据库中是否已存在该文件名
            stmt = select(KnowledgeBase).where(
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.file_name == file_name
            )
            existing_file = db.execute(stmt).scalar_one_or_none()
            if existing_file:
                existing_files.append(file_name)
        
        if existing_files:
            raise HTTPException(
                status_code=400,
                detail=f"以下文件已存在，请勿重复上传: {', '.join(existing_files)}"
            )

        # 处理文件上传
        successful_files = []
        failed_files = []
        
        for file in files:
            file_name = file.filename
            file_path = os.path.join(session_dir, file_name)
            
            try:
                # 读取文件内容
                file_content = await file.read()
                
                # 验证文件内容不为空
                if not file_content:
                    failed_files.append(f"{file_name}: 文件内容为空")
                    continue
                
                # 对于 Excel 文件，进行额外验证
                if file_name.lower().endswith(('.xlsx', '.xls')):
                    # 检查文件头，xlsx 文件应该是 ZIP 格式
                    if file_name.lower().endswith('.xlsx'):
                        # XLSX 文件应该以 PK 开头（ZIP 文件头）
                        if not file_content.startswith(b'PK'):
                            failed_files.append(f"{file_name}: 不是有效的 XLSX 文件格式，可能是 XLS 文件")
                            continue
                    elif file_name.lower().endswith('.xls'):
                        # XLS 文件有特定的文件头
                        if not (file_content.startswith(b'\xd0\xcf\x11\xe0') or 
                               file_content.startswith(b'\x09\x08')):
                            failed_files.append(f"{file_name}: 不是有效的 XLS 文件格式")
                            continue
                
                # 保存文件到本地
                with open(file_path, "wb") as buffer:
                    buffer.write(file_content)
                
                # 验证文件大小
                if os.path.getsize(file_path) != len(file_content):
                    failed_files.append(f"{file_name}: 文件保存失败，大小不匹配")
                    continue
                
                # 保存文件 URL 和 Base64 编码的文件流
                file_url = f"{storage_dir}/{session_id}/{file_name}"
                logger.info(f"Processing file: {file_url}")

                # 尝试解析和插入文档
                try:
                    execute_insert_process(file_url, file_name, session_id)
                    logger.info(f"数据插入es成功: {file_name}")
                    
                    insert_knowledgebase(user_id, file_name)
                    logger.info(f"数据插入pg成功: {file_name}")
                    
                    # 同步数据至管理员知识库管理表（第六阶段全局管理）
                    try:
                        from service.knowledge_sync import add_document_to_admin_kb
                        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                        add_document_to_admin_kb(db, user_id, file_name, file_size)
                    except Exception as sync_err:
                        logger.error(f"写入管理员知识库表失败: {sync_err}")
                    
                    successful_files.append(file_name)
                    
                except Exception as parse_error:
                    logger.error(f"文件解析失败 {file_name}: {str(parse_error)}")
                    failed_files.append(f"{file_name}: 文件解析失败 - {str(parse_error)}")
                    # 删除已保存的文件
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    continue
                        
            except Exception as e:
                logger.error(f"处理文件失败 {file_name}: {str(e)}")
                failed_files.append(f"{file_name}: 处理失败 - {str(e)}")
                continue

        # 构建返回结果
        if successful_files and not failed_files:
            return {
                "status": "success",
                "message": "所有文件解析成功",
                "successful_files": successful_files,
                "total_files": len(files)
            }
        elif successful_files and failed_files:
            return {
                "status": "partial_success",
                "message": f"部分文件解析成功，{len(successful_files)} 个成功，{len(failed_files)} 个失败",
                "successful_files": successful_files,
                "failed_files": failed_files,
                "total_files": len(files)
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "failed",
                    "message": "所有文件解析失败",
                    "failed_files": failed_files,
                    "total_files": len(files)
                }
            )
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

##################################
# 查询会话文档上传信息接口
##################################

@router.get("/sessions/{session_id}/documents", response_model=SessionDocumentsResponse)
async def get_session_documents(
    session_id: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    """
    获取指定会话的所有文档上传记录
    """
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 获取会话的所有文档记录
        documents = DocumentUploadService.get_session_documents(db, session_id)
        has_documents = len(documents) > 0
        
        return SessionDocumentsResponse(
            session_id=session_id,
            has_documents=has_documents,
            documents=[DocumentUploadResponse.from_orm(doc) for doc in documents],
            total_count=len(documents)
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"获取会话文档信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/sessions/{session_id}/documents/summary", response_model=SessionDocumentSummary)
async def get_session_document_summary(
    session_id: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    """
    获取指定会话的文档上传摘要信息
    """
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 检查是否有上传的文档
        has_documents = DocumentUploadService.has_uploaded_documents(db, session_id)
        
        # 获取最新的文档信息
        latest_document = DocumentUploadService.get_latest_document(db, session_id)
        
        # 获取总文档数量
        all_documents = DocumentUploadService.get_session_documents(db, session_id)
        total_documents = len(all_documents)
        
        return SessionDocumentSummary(
            session_id=session_id,
            has_documents=has_documents,
            latest_document_name=latest_document.document_name if latest_document else None,
            latest_document_type=latest_document.document_type if latest_document else None,
            latest_upload_time=latest_document.upload_time if latest_document else None,
            total_documents=total_documents
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"获取会话文档摘要失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
