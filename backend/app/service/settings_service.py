import copy
import json
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.system_config import SystemConfig


SETTINGS_KEY = "rag_settings"
DEEPSEEK_CHAT_ENV_NAMES = ("DEEPSEEK_BASE_URL", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL")

DEFAULT_RAG_SETTINGS: dict[str, Any] = {
    "upload": {
        "maxFileSize": 50 * 1024 * 1024,
        "maxRequestSize": 60 * 1024 * 1024,
    },
    "rag": {
        "default": {
            "collectionName": "swxy",
            "dimension": 1536,
            "metricType": "cosine",
        },
        "retrieval": {
            "topK": 5,
            "vectorSimilarityWeight": 0.6,
            "similarityThreshold": 0.1,
            "candidateTop": 1024,
            "rerankEnabled": True,
        },
        "generation": {
            "temperature": 0.7,
            "promptTemplate": (
                "你是一个专业的智能助手，擅长基于提供的参考资料回答用户问题。请严格遵循以下规范执行任务：\n\n"
                "### 回答前置要求\n"
                "1. **相关性前置校验**：首先逐条审视所有参考内容，逐一判断每条内容与用户问题的匹配度：\n"
                "   - 若参考内容仅为部分相关（例如用户询问完整报销流程，但参考内容仅涉及流程升级后的变更点；或用户询问全品类补贴标准，参考内容仅覆盖单一品类），必须在回答的最开头以醒目的格式明确告知用户：「当前知识库中未找到直接相关的完整文档，检索到的内容仅涉及XX方面，可能无法完整回答您的问题」，严禁将部分相关内容包装为完整答案输出。\n"
                "   - 若参考内容完全无法回应用户问题或与问题完全无关，必须诚实说明「现有参考内容无法解答您的问题」，不得强行拼凑信息生成回答。\n\n"
                "2. **规则完备性自检**：在所有需要做出判断或计算的问题中，必须逐项检查参考内容是否包含了做出该项判断/计算所必须的完整、明确的规则依据：\n"
                "   - 若参考内容中缺少任何一项判断或计算所需的明确规则（例如：仅写了补贴标准金额但未写明天数如何计算、仅写了适用范围但未写明例外情况、仅写了流程步骤但未写明前置条件），必须认定该问题无法被精确回答。\n"
                "   - 在此情况下，必须在回答的最开头以醒目的格式明确告知用户：「当前知识库中缺少 [具体缺失的规则内容] 的明确规定，因此无法给出精确答案。建议您咨询公司行政部门或查阅最新的完整版制度手册。」\n"
                "   - 严禁使用常识推理、类推或日常经验来填补知识库规则的空白。例如：知识库只写了「补贴100元/天」但没有定义「半天如何计算天数」时，不得自行推算天数，必须直接说明规则缺失。\n\n"
                "3. **不确定词汇禁令**：回答中严禁出现以下任何不确定性词汇或表述方式：\n"
                "   - 禁止词汇：「应该」、「可能」、「大概」、「或许」、「估计」、「按常理」、「一般来说」、「通常情况下」、「可以认为」\n"
                "   - 禁止句式：「根据常识...」、「按照一般理解...」、「推断...」、「推测...」、「综合考虑...」\n"
                "   - 当知识库规则不足以给出确定性答案时，必须使用规则完备性自检中的模板句式明确告知用户无法回答，不得使用上述不确定词汇作为软性过渡。\n\n"
                "4. **内容引用规则**：所有输出内容必须优先依托参考内容生成，确保答案准确可靠，不得添加任何参考内容以外的主观信息或外部知识。每一段输出的内容都必须标注对应引用来源，格式统一为：##引用编号$$，例如参考内容中标注的##1$$，需在引用该内容的对应段落前直接使用相同格式标注，严禁使用[N]、[1]等任何其他引用格式。\n\n"
                "5. **计算校验要求**：如果参考内容中包含细项拆分的数值类信息（例如餐补按早餐/午餐/晚餐分别列明金额、交通补按不同出行场景拆分标准），必须严格对照用户问题中提供的个人实际情况，按细项逐条核对计算，不得笼统汇总或估算。\n\n"
                "### 输出格式要求\n"
                "最终输出的回答需条理清晰、逻辑严谨、简明扼要，语言自然流畅，符合专业问答的表达规范，所有引用标注准确对应来源内容，不得出现引用与内容不匹配的情况。\n\n"
                "### 输入素材\n"
                "**参考内容：**\n"
                "{references}\n\n"
                "**用户问题：**\n"
                "{question}\n\n"
                "请基于以上所有要求和素材，提供专业、准确的回答。"
            ),
        },
        "queryRewrite": {"enabled": False},
        "rateLimit": {
            "global": {
                "enabled": False,
                "maxConcurrent": 4,
                "maxWaitSeconds": 30,
                "leaseSeconds": 60,
                "pollIntervalMs": 500,
            }
        },
        "memory": {
            "historyKeepTurns": 10,
            "summaryStartTurns": 20,
            "summaryEnabled": False,
            "summaryMaxChars": 2000,
            "titleMaxLength": 30,
        },
    },
    "ai": {
        "providers": {
            "dashscope": {
                "url": "",
                "apiKey": None,
                "endpoints": {},
            }
        },
        "selection": {
            "failureThreshold": 3,
            "openDurationMs": 30000,
        },
        "stream": {
            "messageChunkSize": 1,
        },
        "chat": {
            "defaultModel": "deepseek-v4-pro",
            "deepThinkingModel": "deepseek-v4-pro",
            "candidates": [
                {
                    "id": "qwen2.5-72b-instruct",
                    "provider": "dashscope",
                    "model": "qwen2.5-72b-instruct",
                    "enabled": True,
                },
                {
                    "id": "deepseek-v4-pro",
                    "provider": "dashscope",
                    "model": "deepseek-v4-pro",
                    "enabled": True,
                    "supportsThinking": True,
                },
            ],
        },
        "embedding": {"defaultModel": "dashscope-embedding", "candidates": []},
        "rerank": {"defaultModel": None, "candidates": []},
    },
}


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def ensure_default_chat_candidates(settings: dict[str, Any]) -> None:
    chat = settings.setdefault("ai", {}).setdefault("chat", {})
    candidates = chat.setdefault("candidates", [])
    if not isinstance(candidates, list):
        candidates = []
        chat["candidates"] = candidates

    existing_ids = {
        str(item.get("id"))
        for item in candidates
        if isinstance(item, dict) and item.get("id")
    }
    default_candidates = DEFAULT_RAG_SETTINGS["ai"]["chat"]["candidates"]
    for candidate in default_candidates:
        candidate_id = str(candidate.get("id"))
        if candidate_id not in existing_ids:
            candidates.append(copy.deepcopy(candidate))
            existing_ids.add(candidate_id)


def load_settings(db: Session) -> dict[str, Any]:
    settings = copy.deepcopy(DEFAULT_RAG_SETTINGS)
    try:
        row = db.scalars(
            select(SystemConfig).where(SystemConfig.config_key == SETTINGS_KEY)
        ).first()
        if row and row.config_value:
            try:
                stored = json.loads(row.config_value)
            except (json.JSONDecodeError, TypeError):
                stored = None
            if isinstance(stored, dict):
                deep_merge(settings, stored)
    except Exception:
        pass
    ensure_default_chat_candidates(settings)
    return settings


def persist_settings(db: Session, settings: dict[str, Any]) -> None:
    payload = json.dumps(settings, ensure_ascii=False)
    try:
        row = db.scalars(
            select(SystemConfig).where(SystemConfig.config_key == SETTINGS_KEY)
        ).first()
        if row:
            row.config_value = payload
        else:
            db.add(SystemConfig(config_key=SETTINGS_KEY, config_value=payload))
        db.commit()
    except Exception:
        db.rollback()
        raise


def sanitize_for_response(settings: dict[str, Any]) -> dict[str, Any]:
    snapshot = copy.deepcopy(settings)
    providers = snapshot.get("ai", {}).get("providers", {})
    if isinstance(providers, dict):
        for provider in providers.values():
            if isinstance(provider, dict):
                provider["apiKey"] = None
    return snapshot


def candidate_model_ids(settings: dict[str, Any]) -> set[str]:
    candidates = settings.get("ai", {}).get("chat", {}).get("candidates", [])
    return {
        str(item["id"]) for item in candidates if isinstance(item, dict) and item.get("id") and item.get("enabled", True)
    }


def validate_settings_patch(payload: dict[str, Any], current: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "settings payload must be an object"

    patch = copy.deepcopy(payload)
    providers = patch.get("ai", {}).get("providers", {})
    if isinstance(providers, dict):
        for provider in providers.values():
            if isinstance(provider, dict):
                provider.pop("apiKey", None)

    retrieval = patch.get("rag", {}).get("retrieval", {})

    top_k = retrieval.get("topK") if isinstance(retrieval, dict) else None
    if top_k is not None:
        try:
            top_k_int = int(top_k)
        except (TypeError, ValueError):
            return None, "topK 必须为整数"
        if top_k_int < 1 or top_k_int > 50:
            return None, "topK 范围：1-50"
        patch["rag"]["retrieval"]["topK"] = top_k_int

    vector_weight = retrieval.get("vectorSimilarityWeight") if isinstance(retrieval, dict) else None
    if vector_weight is not None:
        try:
            vector_weight_value = float(vector_weight)
        except (TypeError, ValueError):
            return None, "vectorSimilarityWeight 必须为数字"
        if vector_weight_value < 0 or vector_weight_value > 1:
            return None, "vectorSimilarityWeight 范围：0-1"
        patch["rag"]["retrieval"]["vectorSimilarityWeight"] = vector_weight_value

    similarity_threshold = retrieval.get("similarityThreshold") if isinstance(retrieval, dict) else None
    if similarity_threshold is not None:
        try:
            similarity_threshold_value = float(similarity_threshold)
        except (TypeError, ValueError):
            return None, "similarityThreshold 必须为数字"
        if similarity_threshold_value < 0 or similarity_threshold_value > 1:
            return None, "similarityThreshold 范围：0-1"
        patch["rag"]["retrieval"]["similarityThreshold"] = similarity_threshold_value

    candidate_top = retrieval.get("candidateTop") if isinstance(retrieval, dict) else None
    if candidate_top is not None:
        try:
            candidate_top_int = int(candidate_top)
        except (TypeError, ValueError):
            return None, "candidateTop 必须为整数"
        if candidate_top_int < 1 or candidate_top_int > 4096:
            return None, "candidateTop 范围：1-4096"
        patch["rag"]["retrieval"]["candidateTop"] = candidate_top_int

    rerank_enabled = retrieval.get("rerankEnabled") if isinstance(retrieval, dict) else None
    if rerank_enabled is not None and not isinstance(rerank_enabled, bool):
        return None, "rerankEnabled 必须为布尔值"

    temperature = patch.get("rag", {}).get("generation", {}).get("temperature")
    if temperature is not None:
        try:
            temperature_value = float(temperature)
        except (TypeError, ValueError):
            return None, "temperature 必须为数字"
        if temperature_value < 0 or temperature_value > 2:
            return None, "temperature 范围：0-2"
        patch["rag"]["generation"]["temperature"] = temperature_value

    prompt = patch.get("rag", {}).get("generation", {}).get("promptTemplate")
    if prompt is not None:
        if not isinstance(prompt, str) or not prompt.strip():
            return None, "promptTemplate 不能为空"
        if len(prompt) > 10000:
            return None, "promptTemplate 不能超过 10000 字符"
        patch["rag"]["generation"]["promptTemplate"] = prompt.strip()

    default_model = patch.get("ai", {}).get("chat", {}).get("defaultModel")
    if default_model is not None:
        model_ids = candidate_model_ids(current)
        if str(default_model) not in model_ids:
            return None, f"defaultModel 必须是启用的候选模型之一: {', '.join(sorted(model_ids))}"

    return patch, None


def get_retrieval_top_k(settings: dict[str, Any]) -> int:
    try:
        return int(settings.get("rag", {}).get("retrieval", {}).get("topK", 5))
    except (TypeError, ValueError):
        return 5


def get_retrieval_config(settings: dict[str, Any]) -> dict[str, Any]:
    retrieval = settings.get("rag", {}).get("retrieval", {})
    top_k = get_retrieval_top_k(settings)
    try:
        vector_similarity_weight = float(retrieval.get("vectorSimilarityWeight", 0.6))
    except (TypeError, ValueError):
        vector_similarity_weight = 0.6
    vector_similarity_weight = min(max(vector_similarity_weight, 0.0), 1.0)

    try:
        similarity_threshold = float(retrieval.get("similarityThreshold", 0.1))
    except (TypeError, ValueError):
        similarity_threshold = 0.1
    similarity_threshold = min(max(similarity_threshold, 0.0), 1.0)

    try:
        candidate_top = int(retrieval.get("candidateTop", 1024))
    except (TypeError, ValueError):
        candidate_top = 1024
    candidate_top = min(max(candidate_top, top_k), 4096)

    return {
        "top_k": top_k,
        "vector_similarity_weight": vector_similarity_weight,
        "similarity_threshold": similarity_threshold,
        "candidate_top": candidate_top,
        "rerank_enabled": bool(retrieval.get("rerankEnabled", True)),
    }


def get_generation_temperature(settings: dict[str, Any]) -> float:
    try:
        return float(settings.get("rag", {}).get("generation", {}).get("temperature", 0.7))
    except (TypeError, ValueError):
        return 0.7


def get_prompt_template(settings: dict[str, Any]) -> str:
    template = settings.get("rag", {}).get("generation", {}).get("promptTemplate")
    if isinstance(template, str) and template.strip():
        return template.strip()
    return DEFAULT_RAG_SETTINGS["rag"]["generation"]["promptTemplate"]


def get_chat_model(settings: dict[str, Any]) -> str:
    configured = settings.get("ai", {}).get("chat", {}).get("defaultModel")
    if configured:
        return str(configured)
    return os.getenv("CHAT_MODEL", "deepseek-v4-pro")


def _env_text(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _deepseek_chat_env_config() -> dict[str, str] | None:
    values = {name: _env_text(name) for name in DEEPSEEK_CHAT_ENV_NAMES}
    if not any(values.values()):
        return None

    missing = [name for name in DEEPSEEK_CHAT_ENV_NAMES if not values[name]]
    if missing:
        raise ValueError(
            "DeepSeek OpenAI 兼容配置不完整，请同时设置: "
            + ", ".join(DEEPSEEK_CHAT_ENV_NAMES)
        )

    return {
        "provider": "deepseek-openai-compatible",
        "base_url": values["DEEPSEEK_BASE_URL"],
        "api_key": values["DEEPSEEK_API_KEY"],
        "model": values["DEEPSEEK_MODEL"],
    }


def get_chat_openai_config(settings: dict[str, Any], fallback_model: str | None = None) -> dict[str, str | None]:
    deepseek_config = _deepseek_chat_env_config()
    if deepseek_config:
        return deepseek_config

    return {
        "provider": "dashscope-openai-compatible",
        "base_url": _env_text("DASHSCOPE_BASE_URL"),
        "api_key": _env_text("DASHSCOPE_API_KEY"),
        "model": fallback_model or get_chat_model(settings),
    }
