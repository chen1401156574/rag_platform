from typing import Any

from fastapi import APIRouter, Depends, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy.orm import Session

from service.auth import access_security
from service.settings_service import (
    DEFAULT_RAG_SETTINGS,
    SETTINGS_KEY,
    deep_merge as _deep_merge,
    load_settings as _load_settings,
    persist_settings as _persist_settings,
    sanitize_for_response as _sanitize_for_response,
    validate_settings_patch as _validate_settings_patch,
)
from utils.database import get_db
from utils.response import error_result, success_result

router = APIRouter()


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
