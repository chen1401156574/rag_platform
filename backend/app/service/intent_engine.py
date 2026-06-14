import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.intent import IntentNode
from service.core.chat import update_session_name, write_chat_to_db
from utils import logger


INTENT_KIND_KB = 0
INTENT_KIND_SYSTEM = 1
INTENT_KIND_MCP = 2


@dataclass
class IntentClassification:
    intent: Optional[IntentNode]
    score: float
    reason: str = ""


@dataclass
class IntentRouteDecision:
    kind: int
    intent: Optional[IntentNode]
    score: float
    reason: str = ""
    collection_name: Optional[str] = None
    kb_ids: Optional[list[str]] = None
    top_k: Optional[int] = None


def _safe_json_loads(raw: Optional[str], fallback: Any = None) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _clean_json_response(raw: str) -> str:
    text = (raw or "").strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _format_examples(node: IntentNode, limit: int = 6) -> list[str]:
    examples = _safe_json_loads(node.examples, [])
    if not isinstance(examples, list):
        return []
    return [str(item) for item in examples[:limit] if str(item).strip()]


def _candidate_text(node: IntentNode) -> str:
    examples = " | ".join(_format_examples(node))
    return (
        f"id={node.id}; code={node.intent_code}; name={node.name}; kind={node.kind}; "
        f"level={node.level}; description={node.description or ''}; examples={examples}"
    )


def _keyword_score(question: str, node: IntentNode) -> float:
    q = question.lower()
    score = 0.0
    if node.name and node.name.lower() in q:
        score += 0.35
    if node.intent_code and node.intent_code.lower() in q:
        score += 0.2
    for example in _format_examples(node, limit=10):
        ex = example.lower()
        if ex and (ex in q or q in ex):
            score += 0.45
    if node.description:
        for token in re.split(r"[,，、\s/]+", node.description.lower()):
            if len(token) >= 2 and token in q:
                score += 0.08
    return min(score, 0.95)


class IntentClassifier:
    def __init__(self, model: Optional[str] = None, min_score: Optional[float] = None):
        self.model = model or os.getenv("INTENT_CLASSIFIER_MODEL", "qwen2.5-7b-instruct")
        default_min_score = 0.55 if min_score is None else min_score
        self.min_score = float(os.getenv("INTENT_CLASSIFIER_MIN_SCORE", default_min_score))

    def load_enabled_intents(self, db: Session) -> list[IntentNode]:
        stmt = (
            select(IntentNode)
            .where(IntentNode.deleted == 0, IntentNode.enabled == 1)
            .order_by(IntentNode.level.desc(), IntentNode.sort_order.asc(), IntentNode.id.asc())
        )
        return list(db.scalars(stmt).all())

    def classify(self, db: Session, question: str) -> IntentClassification:
        intents = self.load_enabled_intents(db)
        if not intents:
            return IntentClassification(intent=None, score=0.0, reason="no enabled intents")

        llm_result = self._classify_with_llm(question, intents)
        if llm_result.intent and llm_result.score >= self.min_score:
            return llm_result

        fallback = self._classify_by_keywords(question, intents)
        if fallback.intent and fallback.score >= min(self.min_score, 0.45):
            return fallback

        return llm_result if llm_result.intent else IntentClassification(intent=None, score=0.0, reason="no confident match")

    def _classify_with_llm(self, question: str, intents: list[IntentNode]) -> IntentClassification:
        candidates = intents[:80]
        candidate_block = "\n".join(f"{idx + 1}. {_candidate_text(node)}" for idx, node in enumerate(candidates))
        prompt = f"""
你是一个用于 RAG 助手的轻量级意图分类器。
请为用户的提问选择一个最匹配的已启用意图。
必须且仅返回严格的 JSON 格式数据：
{{
  "intent_code": "匹配的候选意图标识，若无匹配则返回 null",
  "score": 0.0,
  "reason": "简短的分类理由"
}}

规则：
- 优先选择最具体（层级更深）的子意图。
- 意图类型（kind）仅作为路由元数据，不能作为评分的捷径。
- 如果没有任何候选意图是合理的匹配，则 intent_code 返回 null，score 返回 0。
- score（置信度得分）必须在 0 到 1 之间。

用户提问：
{question}

启用的意图候选列表：
{candidate_block}
""".strip()

        try:
            client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url=os.getenv("DASHSCOPE_BASE_URL"),
            )
            completion = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                stream=False,
                timeout=20,
            )
            raw = completion.choices[0].message.content if completion.choices else ""
            payload = json.loads(_clean_json_response(raw))
            code = payload.get("intent_code")
            score = float(payload.get("score") or 0)
            reason = str(payload.get("reason") or "")
            if not code:
                return IntentClassification(intent=None, score=score, reason=reason or "llm returned null")
            matched = next((node for node in candidates if node.intent_code == code), None)
            return IntentClassification(intent=matched, score=score, reason=reason)
        except Exception as exc:
            logger.warning(f"IntentClassifier LLM classification failed: {exc}")
            return IntentClassification(intent=None, score=0.0, reason=f"llm failed: {exc}")

    def _classify_by_keywords(self, question: str, intents: list[IntentNode]) -> IntentClassification:
        scored = [(_keyword_score(question, node), node) for node in intents]
        scored.sort(key=lambda item: (item[0], item[1].level or 0), reverse=True)
        best_score, best_node = scored[0]
        if best_score <= 0:
            return IntentClassification(intent=None, score=0.0, reason="keyword fallback no match")
        return IntentClassification(intent=best_node, score=best_score, reason="keyword fallback")


class IntentRouter:
    def __init__(self, classifier: Optional[IntentClassifier] = None):
        self.classifier = classifier or IntentClassifier()

    def decide(self, db: Session, question: str, user_id: str) -> IntentRouteDecision:
        classification = self.classifier.classify(db, question)
        intent = classification.intent

        return IntentRouteDecision(
            kind=INTENT_KIND_KB,
            intent=intent,
            score=classification.score,
            reason=classification.reason,
            collection_name=user_id,
            kb_ids=None,
            top_k=5,
        )


def default_intent_router() -> IntentRouter:
    return IntentRouter()


def render_template(template: Optional[str], question: str, intent: Optional[IntentNode], extra: Optional[dict[str, Any]] = None) -> str:
    if not template:
        return ""
    values = {
        "question": question,
        "intent_code": intent.intent_code if intent else "",
        "intent_name": intent.name if intent else "",
        "prompt_snippet": intent.prompt_snippet if intent else "",
    }
    if extra:
        values.update(extra)
    try:
        return template.format(**values)
    except Exception:
        return template


def _stream_text_answer(session_id: str, question: str, answer: str, user_id: str, metadata: dict[str, Any]):
    yield f"event: message\ndata: {json.dumps({'documents': [], 'intent': metadata}, ensure_ascii=False)}\n\n"
    if answer:
        yield f"event: message\ndata: {json.dumps({'role': 'assistant', 'content': answer, 'thinking': False}, ensure_ascii=False)}\n\n"
    yield "event: end\ndata: [DONE]\n\n"
    try:
        write_chat_to_db(session_id, question, answer, [metadata], [], "")
        update_session_name(session_id, question, user_id)
    except Exception as exc:
        logger.warning(f"Failed to persist routed answer: {exc}")


def _general_chat_answer(question: str, intent: Optional[IntentNode]) -> str:
    prompt = render_template(intent.prompt_template if intent else None, question, intent)
    if not prompt:
        prompt = (
            "You are a concise assistant. Answer the user's casual/system interaction directly. "
            "Do not perform knowledge-base retrieval.\n\n"
            f"User question: {question}"
        )
    try:
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL"),
        )
        completion = client.chat.completions.create(
            model=os.getenv("SYSTEM_CHAT_MODEL", "qwen2.5-7b-instruct"),
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            timeout=30,
        )
        return completion.choices[0].message.content if completion.choices else ""
    except Exception as exc:
        logger.warning(f"System intent chat failed: {exc}")
        return "您好，我是智能文档问答助手，可以帮您检索知识库、解析临时文档并回答相关问题。"


def stream_system_intent_response(session_id: str, question: str, user_id: str, decision: IntentRouteDecision):
    intent = decision.intent
    static_answer = render_template(intent.prompt_snippet if intent else None, question, intent)
    answer = static_answer or _general_chat_answer(question, intent)
    metadata = {
        "route": "SYSTEM",
        "intentCode": intent.intent_code if intent else None,
        "intentName": intent.name if intent else None,
        "score": decision.score,
        "reason": decision.reason,
    }
    return _stream_text_answer(session_id, question, answer, user_id, metadata)


def extract_mcp_params(question: str, intent: Optional[IntentNode]) -> dict[str, Any]:
    fallback = _fallback_params(question)
    prompt_template = intent.param_prompt_template if intent else None
    prompt = render_template(prompt_template, question, intent) if prompt_template else ""
    if not prompt:
        prompt = f"""
Extract structured parameters for a tool call from the user question.
Return strict JSON only. Include keys such as metric, time_range, dimension, filters when present.

Question: {question}
""".strip()

    try:
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL"),
        )
        completion = client.chat.completions.create(
            model=os.getenv("MCP_PARAM_MODEL", "qwen2.5-7b-instruct"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            stream=False,
            timeout=20,
        )
        raw = completion.choices[0].message.content if completion.choices else "{}"
        parsed = json.loads(_clean_json_response(raw))
        if isinstance(parsed, dict):
            return {**fallback, **parsed}
    except Exception as exc:
        logger.warning(f"MCP parameter extraction failed: {exc}")
    return fallback


def _fallback_params(question: str) -> dict[str, Any]:
    metric = None
    for key in ["销售额", "销售量", "趋势", "预测", "指标"]:
        if key in question:
            metric = key
            break
    time_range = None
    for key in ["今天", "昨日", "昨天", "本周", "本月", "本季度", "今年", "近7天", "近30天"]:
        if key in question:
            time_range = key
            break
    return {"metric": metric, "time_range": time_range}


def _tool_env_url(tool_id: str) -> Optional[str]:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", tool_id).strip("_").upper()
    return os.getenv(f"MCP_TOOL_{normalized}_URL")


def invoke_mcp_tool(tool_id: str, question: str, params: dict[str, Any], session_id: str, user_id: str, intent: Optional[IntentNode]) -> dict[str, Any]:
    url = tool_id if tool_id.startswith(("http://", "https://")) else _tool_env_url(tool_id)
    payload = {
        "question": question,
        "params": params,
        "sessionId": session_id,
        "userId": user_id,
        "intentCode": intent.intent_code if intent else None,
    }
    if url:
        try:
            response = httpx.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return {"ok": True, "toolId": tool_id, "url": url, "data": data}
        except Exception as exc:
            logger.warning(f"MCP tool call failed: tool_id={tool_id}, error={exc}")
            return {"ok": False, "toolId": tool_id, "error": str(exc), "params": params}

    return {
        "ok": False,
        "toolId": tool_id,
        "error": "tool endpoint is not configured",
        "params": params,
        "hint": f"Set MCP_TOOL_{re.sub(r'[^A-Za-z0-9]+', '_', tool_id).strip('_').upper()}_URL or use an HTTP URL as mcpToolId.",
    }


def _format_tool_answer(question: str, intent: Optional[IntentNode], params: dict[str, Any], tool_result: dict[str, Any]) -> str:
    if tool_result.get("ok"):
        data = tool_result.get("data")
        if isinstance(data, dict):
            for key in ("answer", "text", "message", "summary"):
                if data.get(key):
                    return str(data[key])
        return "工具调用完成，返回结果如下：\n\n```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```"

    return (
        f"已识别为工具调用意图：{intent.name if intent else 'MCP'}。\n\n"
        f"工具 `{tool_result.get('toolId')}` 暂未完成服务端配置，当前仅完成参数提取：\n\n"
        "```json\n"
        + json.dumps(params, ensure_ascii=False, indent=2)
        + "\n```"
    )


def stream_mcp_intent_response(session_id: str, question: str, user_id: str, decision: IntentRouteDecision):
    intent = decision.intent
    tool_id = intent.mcp_tool_id if intent else ""
    params = extract_mcp_params(question, intent)
    tool_result = invoke_mcp_tool(tool_id, question, params, session_id, user_id, intent) if tool_id else {
        "ok": False,
        "toolId": None,
        "error": "intent has no mcp_tool_id",
        "params": params,
    }
    answer = _format_tool_answer(question, intent, params, tool_result)
    metadata = {
        "route": "MCP",
        "intentCode": intent.intent_code if intent else None,
        "intentName": intent.name if intent else None,
        "score": decision.score,
        "reason": decision.reason,
        "toolId": tool_id,
        "params": params,
        "toolResult": tool_result,
    }
    return _stream_text_answer(session_id, question, answer, user_id, metadata)
