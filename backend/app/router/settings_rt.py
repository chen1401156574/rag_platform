import copy
import json
from typing import Any

from fastapi import APIRouter, Depends, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.system_config import SystemConfig
from service.auth import access_security
from utils.database import get_db
from utils.response import error_result, success_result

router = APIRouter()

SETTINGS_KEY = "rag_settings"

DEFAULT_RAG_SETTINGS: dict[str, Any] = {
    "rag": {
        "retrieval": {"topK": 5},
        "generation": {
            "temperature": 0.7,
            "promptTemplate": (
                "请基于给定文档内容回答用户问题。优先使用文档事实；"
                "如果文档中没有答案，请明确说明无法从现有知识库确认。\n\n"
                "用户问题：{question}"
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
        "chat": {
            "defaultModel": "qwen2.5-72b-instruct",
            "deepThinkingModel": "deepseek-r1",
            "candidates": [
                {"id": "qwen2.5-72b-instruct", "provider": "dashscope", "model": "qwen2.5-72b-instruct", "enabled": True},
                {"id": "deepseek-r1", "provider": "dashscope", "model": "deepseek-r1", "enabled": True, "supportsThinking": True},
            ],
        },
        "embedding": {"defaultModel": "dashscope-embedding", "candidates": []},
        "rerank": {"defaultModel": None, "candidates": []},
    },
}


def _load_settings(db: Session) -> dict[str, Any]:
    try:
        row = db.scalars(
            select(SystemConfig).where(SystemConfig.config_key == SETTINGS_KEY)
        ).first()
        if row and row.config_value:
            try:
                return json.loads(row.config_value)
            except (json.JSONDecodeError, TypeError):
                pass
    except Exception:
        pass
    return copy.deepcopy(DEFAULT_RAG_SETTINGS)


def _persist_settings(db: Session, settings: dict[str, Any]) -> None:
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


def _sanitize_for_response(settings: dict[str, Any]) -> dict[str, Any]:
    snapshot = copy.deepcopy(settings)
    providers = snapshot.get("ai", {}).get("providers", {})
    if isinstance(providers, dict):
        for p in providers.values():
            if isinstance(p, dict):
                p["apiKey"] = None
    return snapshot


def _candidate_model_ids(settings: dict[str, Any]) -> set[str]:
    candidates = settings.get("ai", {}).get("chat", {}).get("candidates", [])
    return {
        str(item["id"]) for item in candidates if isinstance(item, dict) and item.get("id") and item.get("enabled", True)
    }


def _validate_settings_patch(payload: dict[str, Any], current: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    patch = copy.deepcopy(payload)
    providers = patch.get("ai", {}).get("providers", {})
    if isinstance(providers, dict):
        for p in providers.values():
            if isinstance(p, dict):
                p.pop("apiKey", None)

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
            t = float(temperature)
        except (TypeError, ValueError):
            return None, "temperature 必须为数字"
        if t < 0 or t > 2:
            return None, "temperature 范围：0-2"
        patch["rag"]["generation"]["temperature"] = t

    prompt = patch.get("rag", {}).get("generation", {}).get("promptTemplate")
    if prompt is not None:
        if not isinstance(prompt, str) or not prompt.strip():
            return None, "promptTemplate 不能为空"
        if len(prompt) > 10000:
            return None, "promptTemplate 不能超过 10000 字符"

    default_model = patch.get("ai", {}).get("chat", {}).get("defaultModel")
    if default_model is not None:
        model_ids = _candidate_model_ids(current)
        if str(default_model) not in model_ids:
            return None, f"defaultModel 必须是启用的候选模型之一: {', '.join(sorted(model_ids))}"

    return patch, None


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


@router.get("/rag/settings")
async def get_settings(
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        return success_result(data=_sanitize_for_response(_load_settings(db)))
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.post("/rag/settings")
async def save_settings(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        current = _load_settings(db)
        patch, error = _validate_settings_patch(payload, current)
        if error:
            return error_result(code="400", message=error)
        _deep_merge(current, patch or {})
        _persist_settings(db, current)
        return success_result(data=_sanitize_for_response(current))
    except Exception as e:
        return error_result(code="500", message=str(e))
