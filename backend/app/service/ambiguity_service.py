"""
歧义检测与追问生成服务

通过信息审计模式检测是否需要追问用户：
1. 列出精确回答所需的全部参数
2. 对比用户问题中已提供的信息
3. 缺失关键参数时生成追问，而非猜测性回答
"""
import json
import os
import re
from typing import Optional

from openai import OpenAI

from utils import logger


def _clean_json(raw: str) -> str:
    text = (raw or "").strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


def _get_ambiguity_model(settings: Optional[dict] = None) -> str:
    if settings:
        model = settings.get("ai", {}).get("ambiguity", {}).get("model")
        if model:
            return model
    return os.getenv("AMBIGUITY_MODEL", os.getenv("CHAT_MODEL", "deepseek-v4-pro"))


def _format_refs(references: list[dict]) -> str:
    ref_texts = []
    for i, ref in enumerate(references[:8]):
        content = ref.get("content_with_weight", "")
        if len(content) > 500:
            content = content[:500] + "..."
        ref_texts.append(f"##{i + 1}$$ {ref.get('document_name', '')}: {content}")
    return "\n\n".join(ref_texts)


def check_draft_and_clarify(
    question: str,
    references: list[dict],
    settings: Optional[dict] = None,
) -> Optional[list[str]]:
    """
    信息审计 + 追问生成。

    流程：
    1. 审计：列出精确回答所需的全部参数
    2. 对比：检查用户问题中已提供哪些信息
    3. 决策：缺失关键参数 → 生成追问；信息完备 → 返回 None
    """
    if not references:
        return None

    ref_block = _format_refs(references)
    model = _get_ambiguity_model(settings)

    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("DASHSCOPE_BASE_URL"),
    )

    # 第1步：信息审计 + 生成追问
    # 核心思想：先审计用户问题缺少什么关键信息，再决定是否追问。
    # 不做草稿回答，因为 LLM 在"先答后审"模式下很难诚实地自我否定。
    draft_prompt = f"""你是一个严谨的审计助手。你的任务不是回答问题，而是判断用户的问题是否能被精确回答。

检索结果：
{ref_block}

用户问题：{question}

请按以下步骤审计，然后返回 JSON：

**第1步：识别问题类型和必需参数**
根据检索结果中的规则或制度，列出要精确回答此问题**必须知道**的所有参数。
例如：差旅报销问题通常需要 → 城市（决定住宿标准）、员工级别（决定住宿标准）、是否产生住宿、酒店是否含餐饮、往返交通方式。

**第2步：对比用户已提供的信息**
检查用户问题中是否明确给出了这些参数。

**第3步：判断与决策**
- 如果有**任何一个**必需参数缺失，则 need_clarify = true，并针对缺失参数生成追问
- 只有当**所有**必需参数都明确提供时，need_clarify 才为 false

返回 JSON 格式：
{{
  "required_params": ["参数1：为什么需要", "参数2：为什么需要"],
  "missing_params": ["缺失参数1", "缺失参数2"],
  "need_clarify": true/false,
  "clarify_questions": ["追问1", "追问2", "追问3"],
  "draft_answer": "仅在 need_clarify=false 时填写草稿回答，否则留空"
}}

重要规则：
- 宁可多问，不可猜测。任何不确定的参数都视为缺失
- clarify_questions 最多3个，要具体、方便用户一次性回答（例如"您出差去哪个城市？您的员工级别是普通员工还是LT成员？"）
- 如果用户问题本身就是闲聊或不涉及计算/规则的问题，need_clarify = false
- 不要返回 markdown 代码块包裹，直接返回 JSON
"""

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": draft_prompt}],
            stream=False,
            timeout=30,
        )
        raw = completion.choices[0].message.content if completion.choices else "{}"
        data = json.loads(_clean_json(raw))

        need_clarify = data.get("need_clarify", False)
        questions = data.get("clarify_questions", [])
        required_params = data.get("required_params", [])
        missing_params = data.get("missing_params", [])
        draft = data.get("draft_answer", "")

        logger.info(f"必需参数: {required_params}")
        logger.info(f"缺失参数: {missing_params}")
        if draft:
            logger.info(f"草稿回答: {draft[:100]}...")

        if need_clarify and isinstance(questions, list) and len(questions) > 0:
            logger.info(f"检测到不确定性，生成 {len(questions)} 个追问")
            return questions

        logger.info("草稿回答无关键不确定性，继续生成正式回答")
        return None

    except Exception as exc:
        logger.warning(f"草稿检测失败，跳过追问：{exc}")
        import traceback
        logger.warning(traceback.format_exc())
        return None


def merge_clarifications(question: str, clarifications: str) -> str:
    """将用户追问回答与原问题合并"""
    return f"""用户原始提问：{question}

用户对追问的补充说明：{clarifications}

请基于以上完整信息生成回答。"""
