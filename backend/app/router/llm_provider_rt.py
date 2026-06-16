import uuid
import httpx
from fastapi import APIRouter, Depends, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select

from service.auth import access_security
from models.llm_provider import LLMProvider
from schemas.llm_provider import (
    LLMProviderCreateRequest,
    LLMProviderUpdateRequest,
    LLMProviderVO,
)
from utils.database import get_db
from utils.response import success_result, error_result
from utils.crypto import encrypt_api_key, decrypt_api_key

router = APIRouter()

MASKED_KEY = "****"


def _to_vo(provider: LLMProvider) -> dict:
    return {
        "id": provider.id,
        "name": provider.name,
        "base_url": provider.base_url,
        "api_key": MASKED_KEY,
        "enabled_models": provider.get_enabled_models(),
        "is_active": provider.is_active,
        "created_at": provider.created_at.isoformat() if provider.created_at else None,
        "updated_at": provider.updated_at.isoformat() if provider.updated_at else None,
    }


@router.get("/llm-providers/list")
async def list_providers(
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        rows = db.scalars(select(LLMProvider).order_by(LLMProvider.created_at.desc())).all()
        return success_result(data=[_to_vo(r) for r in rows])
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.post("/llm-providers/create")
async def create_provider(
    payload: LLMProviderCreateRequest,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        provider_id = str(uuid.uuid4()).replace("-", "")[:20]
        encrypted = encrypt_api_key(payload.api_key)
        provider = LLMProvider(
            id=provider_id,
            name=payload.name,
            base_url=payload.base_url.rstrip("/"),
            encrypted_api_key=encrypted,
        )
        db.add(provider)
        db.commit()
        return success_result(data=_to_vo(provider))
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))


@router.put("/llm-providers/{provider_id}")
async def update_provider(
    provider_id: str,
    payload: LLMProviderUpdateRequest,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        provider = db.scalars(
            select(LLMProvider).where(LLMProvider.id == provider_id)
        ).first()
        if not provider:
            return error_result(code="404", message="提供商不存在")

        if payload.name is not None:
            provider.name = payload.name
        if payload.base_url is not None:
            provider.base_url = payload.base_url.rstrip("/")
        if payload.api_key is not None:
            provider.encrypted_api_key = encrypt_api_key(payload.api_key)
        if payload.enabled_models is not None:
            provider.set_enabled_models(payload.enabled_models)
        if payload.is_active is not None:
            provider.is_active = payload.is_active

        db.commit()
        return success_result(data=_to_vo(provider))
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))


@router.delete("/llm-providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        provider = db.scalars(
            select(LLMProvider).where(LLMProvider.id == provider_id)
        ).first()
        if not provider:
            return error_result(code="404", message="提供商不存在")
        db.delete(provider)
        db.commit()
        return success_result(message="已删除")
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))


@router.post("/llm-providers/{provider_id}/fetch-models")
async def fetch_models(
    provider_id: str,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        provider = db.scalars(
            select(LLMProvider).where(LLMProvider.id == provider_id)
        ).first()
        if not provider:
            return error_result(code="404", message="提供商不存在")

        api_key = decrypt_api_key(provider.encrypted_api_key)
        url = f"{provider.base_url}/models"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code != 200:
            detail = resp.text[:500]
            return error_result(code="400", message=f"获取模型列表失败 ({resp.status_code}): {detail}")

        data = resp.json()
        raw_models = data.get("data", []) if isinstance(data, dict) else []
        model_ids = sorted(
            {m["id"] for m in raw_models if isinstance(m, dict) and m.get("id")}
        )
        return success_result(data={"models": model_ids})
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.post("/llm-providers/{provider_id}/test")
async def test_connection(
    provider_id: str,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        provider = db.scalars(
            select(LLMProvider).where(LLMProvider.id == provider_id)
        ).first()
        if not provider:
            return error_result(code="404", message="提供商不存在")

        api_key = decrypt_api_key(provider.encrypted_api_key)
        url = f"{provider.base_url}/models"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code == 200:
            return success_result(message="连接正常")
        return error_result(code="400", message=f"连接失败 ({resp.status_code})")
    except Exception as e:
        return error_result(code="500", message=str(e))
