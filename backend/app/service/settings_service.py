import copy
import json
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.system_config import SystemConfig


SETTINGS_KEY = "rag_settings"

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
        "retrieval": {"topK": 5},
        "generation": {
            "temperature": 0.7,
            "promptTemplate": (
                "你是一个专业的智能助手，擅长基于提供的参考资料回答用户问题。请遵循以下原则：\n\n"
                "**回答要求：**\n"
                "1. 优先基于参考内容回答，确保答案准确可靠\n"
                "2. 在回答中，每一块内容都必须标注引用来源，格式为：##引用编号$$。例如：##1$$ 表示引用自第1条参考内容。\n"
                "3. 如果参考内容不足以完全回答问题，可以结合常识补充，但需明确区分\n"
                "4. 回答要条理清晰、语言自然流畅\n"
                "5. 如果没有相关参考内容，请诚实说明并提供一般性建议\n\n"
                "**参考内容：**\n"
                "{references}\n\n"
                "**用户问题：**\n"
                "{question}\n\n"
                "请基于以上信息提供专业、准确的回答。"
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

    top_k = patch.get("rag", {}).get("retrieval", {}).get("topK")
    if top_k is not None:
        try:
            top_k_int = int(top_k)
        except (TypeError, ValueError):
            return None, "topK 必须为整数"
        if top_k_int < 1 or top_k_int > 50:
            return None, "topK 范围：1-50"
        patch["rag"]["retrieval"]["topK"] = top_k_int

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
