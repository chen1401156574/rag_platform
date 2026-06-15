from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.orm import Session
from utils.database import get_db
from models.message import KnowledgeBase  
from schemas.message import FilestResponse , SessionListResponse, SessionResponse
from fastapi_jwt import JwtAuthorizationCredentials
from service.auth import access_security
from typing import List
from sqlalchemy import inspect, text ,select
from urllib.parse import unquote
from service.document_operations import delete_document
import json
import re

router = APIRouter()

_MERGED_CLARIFICATION_RE = re.compile(
    r"^\s*用户原始提问：(?P<original>.*?)\s*用户对追问的补充说明：(?P<clarifications>.*?)\s*请基于以上完整信息生成回答。\s*$",
    re.S,
)


def _parse_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_legacy_merged_question(question: str | None) -> dict:
    if not question:
        return {}
    match = _MERGED_CLARIFICATION_RE.match(question)
    if not match:
        return {}
    return {
        "original_question": match.group("original").strip(),
        "clarifications": match.group("clarifications").strip(),
        "effective_question": question,
        "legacy_merged_clarification": True,
    }


def _messages_select_sql(db: Session) -> str:
    inspector = inspect(db.get_bind())
    columns = {column["name"] for column in inspector.get_columns("messages")}
    message_type_expr = "message_type" if "message_type" in columns else "'answer' AS message_type"
    metadata_json_expr = "metadata_json" if "metadata_json" in columns else "NULL AS metadata_json"
    return f"""
        SELECT
            message_id,
            session_id,
            user_question,
            model_answer,
            documents,
            recommended_questions,
            think,
            created_at,
            {message_type_expr},
            {metadata_json_expr}
        FROM messages
        WHERE session_id = :session_id
        ORDER BY created_at ASC
    """


def _message_record(message) -> dict:
    metadata = _parse_metadata(message.metadata_json)
    legacy = _parse_legacy_merged_question(message.user_question)
    if legacy:
        metadata = {**legacy, **metadata}

    message_type = message.message_type or "answer"
    if legacy and message_type == "answer":
        user_question = metadata.get("clarifications") or message.user_question
    else:
        user_question = message.user_question

    return {
        "message_id": message.message_id,
        "session_id": message.session_id,
        "user_question": user_question,
        "model_answer": message.model_answer,
        "documents": message.documents,
        "recommended_questions": message.recommended_questions,
        "think": message.think,
        "message_type": message_type,
        "metadata_json": message.metadata_json,
        "original_question": metadata.get("original_question"),
        "clarifications": metadata.get("clarifications"),
        "clarifying_questions": metadata.get("clarifying_questions") or [],
        "legacy_merged_clarification": bool(metadata.get("legacy_merged_clarification")),
        "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S")
    }

############################
#   获取文档列表
############################

@router.get("/get_files", response_model=List[FilestResponse])
async def get_documents_by_user_id(
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    """
    获取用户上传的文档列表，需要用户认证
    """
    try:
        # 从 token 中获取用户 ID
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 构建查询语句
        stmt = select(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
        
        # 执行查询
        result = db.execute(stmt).scalars().all()

        # 如果没有找到文档，返回空列表
        if not result:
            return []

        # 将查询结果转换为 Pydantic 模型
        documents = [
            FilestResponse(
                user_id=row.user_id,
                file_name=row.file_name,
                created_at=row.created_at.isoformat(),
                updated_at=row.updated_at.isoformat()
            )
            for row in result
        ]

        return documents

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve documents: {str(e)}"
        )

############################
#   删除文档
############################

@router.delete("/delete_file/{file_name}")
async def delete_document_endpoint(
    file_name: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        # URL 解码文件名
        decoded_file_name = unquote(file_name)
        
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 调用 service 层的删除方法
        result = delete_document(user_id, decoded_file_name, db)
        
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])
            
        return {"message": result["message"]}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_messages")
async def get_messages_by_session_id(
    session_id: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 查询 messages 表中对应 session_id 的消息
        messages_data = db.execute(text(_messages_select_sql(db)), {"session_id": session_id}).fetchall()

        # 构造返回数据
        messages = [_message_record(message) for message in messages_data]

        return messages

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve messages: {str(e)}"
        )
    
@router.get("/get_sessions", response_model=SessionListResponse)
async def get_sessions_by_user_id(
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")


        # 查询 sessions 表中对应 user_id 的所有会话
        sessions_data = db.execute(
            text("SELECT * FROM sessions WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).fetchall()

        # 构造返回数据
        sessions = []
        for session in sessions_data:
            sessions.append(
                SessionResponse(
                    session_id=session.session_id,
                    session_name=session.session_name,
                    user_id=session.user_id,
                    created_at=session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    updated_at=session.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                )
            )

        return {"user_id": user_id, "sessions": sessions}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
