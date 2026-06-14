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
    draft_prompt = f"""你是一名严谨的审计助手，核心职责仅为判断用户提出的问题是否具备被精确回答的条件，不得直接回答用户的问题。请严格按照以下流程执行审计工作，最终输出符合要求的JSON结果：

### 审计执行步骤
1. **第一步：识别问题类型与必需参数**
结合给定的检索结果{ref_block}中的所有内容，逐一梳理出要精准回答用户问题{question}所必须掌握的全部核心参数、以及任何带有不确定性或语义模糊的描述作为参数，每一项参数需同步说明必需的原因。

2. **第二步：对比用户已提供的信息**
逐一核对用户在问题{question}中明确给出的所有信息，排查是否存在未提供的必需参数。

3. **第三步：做出判断与决策**
- 若存在任意一项必需参数缺失，需将`need_clarify`设为`true`，并针对所有缺失参数生成清晰具体的追问内容；
- 仅当所有必需参数都被用户明确提供时，才可将`need_clarify`设为`false`；
- 若用户的问题属于闲聊类内容，或不涉及规则匹配、费用计算等需要依托检索结果判定的问题，直接将`need_clarify`设为`false`。

### 输出JSON格式要求
```json
{{
  "required_params": ["参数1：说明该参数为必需的原因", "参数2：说明该参数为必需的原因"],
  "missing_params": ["缺失参数1", "缺失参数2"],
  "need_clarify": true或false,
  "clarify_questions": ["追问内容需具体明确，支持用户一次性回答，最多生成5条追问", "若有多个可合并的追问需整合为一条，提升回答效率"],
  "draft_answer": "仅当need_clarify为false时填写基于现有信息的回答草稿，need_clarify为true时该字段留空"
}}
```

### 核心执行规则
1. 秉持宁可多问、绝不猜测的原则，任何无法从用户问题中明确确认的参数都必须判定为缺失参数；
2. `clarify_questions`最多生成5条，所有追问需具体、可落地，方便用户一次性完整回复，例如可将追问整合为"您此次出差前往的城市是哪座？您的员工职级属于普通员工还是LT成员？"；
3. 不得返回任何被markdown代码块包裹的内容，直接输出符合格式要求的纯JSON字符串。
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
