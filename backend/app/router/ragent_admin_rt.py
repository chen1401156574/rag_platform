from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from models.message import Message
from models.session import Session as ChatSession
from service.auth import access_security
from utils.database import get_db
from utils.response import success_result

router = APIRouter()


def _page(records: list[dict[str, Any]], total: int = 0, current: int = 1, size: int = 10) -> dict[str, Any]:
    page_size = max(size, 1)
    return {
        "records": records,
        "total": total,
        "size": size,
        "current": current,
        "pages": (total + page_size - 1) // page_size,
    }


def _dt(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _current_user_id(credentials: JwtAuthorizationCredentials) -> str:
    return str((credentials.subject or {}).get("user_id", ""))


# 该文件仅保留暂未拆出专门 router 的 Ragent 兼容端点。
# dashboard、knowledge-base、ingestion、trace、settings 等真实业务实现均由专门 router 承载。


@router.get("/mappings")
async def get_mappings(current: int = 1, size: int = 10, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_page([], 0, current, size))


@router.post("/mappings")
async def create_mapping(_: dict[str, Any], __: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=uuid4().hex[:16])


@router.put("/mappings/{mapping_id}")
async def update_mapping(mapping_id: str, _: dict[str, Any], __: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=mapping_id)


@router.delete("/mappings/{mapping_id}")
async def delete_mapping(mapping_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=mapping_id)


@router.get("/rag/sample-questions")
async def list_sample_questions(_: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=[])


@router.get("/sample-questions")
async def get_sample_questions(current: int = 1, size: int = 10, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_page([], 0, current, size))


@router.post("/sample-questions")
async def create_sample_question(_: dict[str, Any], __: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=uuid4().hex[:16])


@router.put("/sample-questions/{question_id}")
async def update_sample_question(question_id: str, _: dict[str, Any], __: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=question_id)


@router.delete("/sample-questions/{question_id}")
async def delete_sample_question(question_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=question_id)


@router.get("/conversations")
async def get_conversations(
    db: DbSession = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    user_id = _current_user_id(credentials)
    rows = db.scalars(select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())).all()
    return success_result(
        data=[
            {
                "conversationId": row.session_id,
                "title": row.session_name,
                "lastTime": _dt(row.updated_at),
            }
            for row in rows
        ]
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=conversation_id)


@router.put("/conversations/{conversation_id}")
async def rename_conversation(conversation_id: str, _: dict[str, Any], __: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=conversation_id)


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    rows = db.scalars(select(Message).where(Message.session_id == conversation_id).order_by(Message.create_time.asc())).all()
    messages = []
    for row in rows:
        messages.append(
            {
                "id": str(row.message_id),
                "conversationId": row.session_id,
                "role": "user",
                "content": row.user_question,
                "thinkingContent": None,
                "thinkingDuration": None,
                "vote": None,
                "createTime": _dt(row.create_time),
            }
        )
        messages.append(
            {
                "id": f"{row.message_id}-assistant",
                "conversationId": row.session_id,
                "role": "assistant",
                "content": row.model_answer,
                "thinkingContent": None,
                "thinkingDuration": None,
                "vote": None,
                "createTime": _dt(row.create_time),
            }
        )
    return success_result(data=messages)


@router.post("/rag/v3/stop")
async def stop_task(taskId: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=taskId)


@router.post("/conversations/messages/{message_id}/feedback")
async def submit_feedback(message_id: str, _: dict[str, Any], __: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=message_id)
