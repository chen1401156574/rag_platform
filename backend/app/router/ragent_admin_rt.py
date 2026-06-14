import copy
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Security, UploadFile
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from models.document_upload import DocumentUpload
from models.message import KnowledgeBase, Message
from models.session import Session as ChatSession
from models.user import User
from service.auth import access_security
from utils.database import get_db
from utils.response import error_result, success_result

router = APIRouter()

DEFAULT_RUNTIME_RAG_SETTINGS: dict[str, Any] = {
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
        },
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
            "defaultModel": "qwen2.5-72b-instruct",
            "deepThinkingModel": "deepseek-r1",
            "candidates": [
                {
                    "id": "qwen2.5-72b-instruct",
                    "provider": "dashscope",
                    "model": "qwen2.5-72b-instruct",
                    "enabled": True,
                },
                {
                    "id": "deepseek-r1",
                    "provider": "dashscope",
                    "model": "deepseek-r1",
                    "enabled": True,
                    "supportsThinking": True,
                },
            ],
        },
        "embedding": {
            "defaultModel": "dashscope-embedding",
            "candidates": [],
        },
        "rerank": {
            "defaultModel": None,
            "candidates": [],
        },
    },
}

_runtime_rag_settings: dict[str, Any] = copy.deepcopy(DEFAULT_RUNTIME_RAG_SETTINGS)


def _page(records: list[dict[str, Any]], total: int = 0, current: int = 1, size: int = 10) -> dict[str, Any]:
    page_size = max(size, 1)
    return {
        "records": records,
        "total": total,
        "size": size,
        "current": current,
        "pages": (total + page_size - 1) // page_size,
    }


def _dt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _current_user_id(credentials: JwtAuthorizationCredentials) -> str:
    return str(credentials.subject.get("user_id", ""))


def _knowledge_base_record(db: DbSession, user_id: str) -> dict[str, Any]:
    rows = db.scalars(select(KnowledgeBase).where(KnowledgeBase.user_id == user_id)).all()
    created_values = [row.created_at for row in rows if row.created_at is not None]
    updated_values = [row.updated_at for row in rows if row.updated_at is not None]
    return {
        "id": user_id,
        "name": f"{user_id} knowledge base",
        "embeddingModel": "dashscope-default",
        "collectionName": user_id,
        "createdBy": user_id,
        "documentCount": len(rows),
        "createTime": _dt(min(created_values)) if created_values else None,
        "updateTime": _dt(max(updated_values)) if updated_values else None,
    }


def _document_record(row: KnowledgeBase) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "kbId": row.user_id,
        "docName": row.file_name,
        "sourceType": "file",
        "sourceLocation": None,
        "scheduleEnabled": 0,
        "scheduleCron": None,
        "enabled": True,
        "chunkCount": 0,
        "fileUrl": None,
        "fileType": row.file_name.rsplit(".", 1)[-1].lower() if "." in row.file_name else None,
        "fileSize": None,
        "processMode": "chunk",
        "chunkStrategy": "fixed_size",
        "chunkConfig": None,
        "pipelineId": None,
        "status": "success",
        "createdBy": row.user_id,
        "updatedBy": row.user_id,
        "createTime": _dt(row.created_at),
        "updateTime": _dt(row.updated_at),
        "chunksEdited": False,
    }


def reset_runtime_rag_settings() -> None:
    _runtime_rag_settings.clear()
    _runtime_rag_settings.update(copy.deepcopy(DEFAULT_RUNTIME_RAG_SETTINGS))


def _deep_update(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def _settings_snapshot() -> dict[str, Any]:
    snapshot = copy.deepcopy(_runtime_rag_settings)
    for provider in snapshot.get("ai", {}).get("providers", {}).values():
        if isinstance(provider, dict):
            provider["apiKey"] = None
    return snapshot


def _candidate_model_ids(settings: dict[str, Any]) -> set[str]:
    candidates = settings.get("ai", {}).get("chat", {}).get("candidates", [])
    return {
        str(item.get("id"))
        for item in candidates
        if isinstance(item, dict) and item.get("id") and item.get("enabled", True)
    }


def _normalize_settings_patch(payload: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[str]]:
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
            return None, "topK must be an integer"
        if top_k_int < 1 or top_k_int > 50:
            return None, "topK must be between 1 and 50"
        patch["rag"]["retrieval"]["topK"] = top_k_int

    temperature = patch.get("rag", {}).get("generation", {}).get("temperature")
    if temperature is not None:
        try:
            temperature_value = float(temperature)
        except (TypeError, ValueError):
            return None, "temperature must be a number"
        if temperature_value < 0 or temperature_value > 2:
            return None, "temperature must be between 0 and 2"
        patch["rag"]["generation"]["temperature"] = temperature_value

    prompt = patch.get("rag", {}).get("generation", {}).get("promptTemplate")
    if prompt is not None:
        if not isinstance(prompt, str) or not prompt.strip():
            return None, "promptTemplate must be a non-empty string"
        if len(prompt) > 10000:
            return None, "promptTemplate must be 10000 characters or fewer"
        patch["rag"]["generation"]["promptTemplate"] = prompt.strip()

    default_model = patch.get("ai", {}).get("chat", {}).get("defaultModel")
    if default_model is not None:
        model_ids = _candidate_model_ids(_runtime_rag_settings)
        if str(default_model) not in model_ids:
            return None, "defaultModel must be one of the enabled chat candidates"

    return patch, None


@router.get("/rag/settings")
async def get_rag_settings(_: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_settings_snapshot())


@router.post("/rag/settings")
async def save_rag_settings(
    payload: dict[str, Any],
    _: JwtAuthorizationCredentials = Security(access_security),
):
    patch, error = _normalize_settings_patch(payload)
    if error:
        return error_result(code="400", message=error)

    _deep_update(_runtime_rag_settings, patch or {})
    return success_result(data=_settings_snapshot())


@router.get("/admin/dashboard/overview")
async def get_dashboard_overview(
    window: str = "24h",
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    users = db.scalar(select(func.count()).select_from(User)) or 0
    sessions = db.scalar(select(func.count()).select_from(ChatSession)) or 0
    messages = db.scalar(select(func.count()).select_from(Message)) or 0
    since = datetime.now() - timedelta(hours=24)
    sessions_24h = db.scalar(select(func.count()).select_from(ChatSession).where(ChatSession.created_at >= since)) or 0
    messages_24h = db.scalar(select(func.count()).select_from(Message).where(Message.create_time >= since)) or 0
    return success_result(
        data={
            "window": window,
            "compareWindow": "previous",
            "updatedAt": int(datetime.now().timestamp() * 1000),
            "kpis": {
                "totalUsers": {"value": users},
                "activeUsers": {"value": users},
                "totalSessions": {"value": sessions},
                "sessions24h": {"value": sessions_24h},
                "totalMessages": {"value": messages},
                "messages24h": {"value": messages_24h},
            },
        }
    )


@router.get("/admin/dashboard/performance")
async def get_dashboard_performance(
    window: str = "24h",
    _: JwtAuthorizationCredentials = Security(access_security),
):
    return success_result(
        data={
            "window": window,
            "avgLatencyMs": 0,
            "p95LatencyMs": 0,
            "successRate": 100,
            "errorRate": 0,
            "noDocRate": 0,
            "slowRate": 0,
        }
    )


@router.get("/admin/dashboard/trends")
async def get_dashboard_trends(
    metric: str,
    window: str = "7d",
    granularity: str = "day",
    _: JwtAuthorizationCredentials = Security(access_security),
):
    now = datetime.now()
    points = []
    for index in range(7):
        ts = now - timedelta(days=6 - index)
        points.append({"ts": int(ts.timestamp() * 1000), "value": 0})
    return success_result(
        data={
            "metric": metric,
            "window": window,
            "granularity": granularity,
            "series": [{"name": metric, "data": points}],
        }
    )


@router.get("/knowledge-base/chunk-strategies")
async def get_chunk_strategies(_: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(
        data=[
            {
                "value": "fixed_size",
                "label": "Fixed size",
                "defaultConfig": {"chunkSize": 512, "overlapSize": 128},
            },
            {
                "value": "semantic",
                "label": "Semantic",
                "defaultConfig": {"targetChars": 1400, "maxChars": 1800, "minChars": 600, "overlapChars": 0},
            },
        ]
    )


@router.get("/knowledge-base")
async def get_knowledge_bases(
    current: int = 1,
    size: int = 10,
    name: Optional[str] = None,
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    user_ids = [row[0] for row in db.execute(select(KnowledgeBase.user_id).distinct()).all()]
    records = [_knowledge_base_record(db, user_id) for user_id in user_ids]
    if name:
        records = [item for item in records if name.lower() in item["name"].lower()]
    total = len(records)
    start = (current - 1) * size
    return success_result(data=_page(records[start : start + size], total, current, size))


@router.get("/knowledge-base/{kb_id}")
async def get_knowledge_base(
    kb_id: str,
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    return success_result(data=_knowledge_base_record(db, kb_id))


@router.post("/knowledge-base")
async def create_knowledge_base(_: dict[str, Any], credentials: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_current_user_id(credentials) or uuid4().hex[:16])


@router.put("/knowledge-base/{kb_id}")
async def update_knowledge_base(kb_id: str, _: dict[str, Any], __: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=kb_id)


@router.delete("/knowledge-base/{kb_id}")
async def delete_knowledge_base(kb_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=kb_id)


@router.get("/knowledge-base/{kb_id}/docs")
async def get_knowledge_documents(
    kb_id: str,
    current: int = 1,
    size: int = 10,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    query = select(KnowledgeBase).where(KnowledgeBase.user_id == kb_id)
    rows = db.scalars(query).all()
    records = [_document_record(row) for row in rows]
    if keyword:
        records = [item for item in records if keyword.lower() in item["docName"].lower()]
    if status:
        records = [item for item in records if item["status"] == status]
    total = len(records)
    start = (current - 1) * size
    return success_result(data=_page(records[start : start + size], total, current, size))


@router.get("/knowledge-base/docs/search")
async def search_knowledge_documents(
    keyword: str = "",
    limit: int = 8,
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    query = select(KnowledgeBase)
    rows = db.scalars(query).all()
    records = [
        {"id": str(row.id), "kbId": row.user_id, "docName": row.file_name, "kbName": f"{row.user_id} knowledge base"}
        for row in rows
        if not keyword or keyword.lower() in row.file_name.lower()
    ]
    return success_result(data=records[:limit])


@router.post("/knowledge-base/{kb_id}/docs/upload")
async def upload_knowledge_document(
    kb_id: str,
    sourceType: str = Form("file"),
    file: Optional[UploadFile] = File(None),
    sourceLocation: Optional[str] = Form(None),
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    doc_name = file.filename if file is not None else sourceLocation or "untitled"
    row = KnowledgeBase(user_id=kb_id, file_name=doc_name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return success_result(data=_document_record(row))


@router.get("/knowledge-base/docs/{doc_id}")
async def get_knowledge_document(
    doc_id: int,
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    row = db.get(KnowledgeBase, doc_id)
    return success_result(data=_document_record(row) if row else None)


@router.put("/knowledge-base/docs/{doc_id}")
async def update_knowledge_document(
    doc_id: int,
    payload: dict[str, Any],
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    row = db.get(KnowledgeBase, doc_id)
    if row and payload.get("docName"):
        row.file_name = payload["docName"]
        db.commit()
    return success_result(data=None)


@router.post("/knowledge-base/docs/{doc_id}/chunk")
async def chunk_knowledge_document(doc_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=doc_id)


@router.patch("/knowledge-base/docs/{doc_id}/enable")
async def enable_knowledge_document(doc_id: str, value: bool = True, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"id": doc_id, "enabled": value})


@router.delete("/knowledge-base/docs/{doc_id}")
async def delete_knowledge_document(
    doc_id: int,
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    row = db.get(KnowledgeBase, doc_id)
    if row:
        db.delete(row)
        db.commit()
    return success_result(data=None)


@router.get("/knowledge-base/docs/{doc_id}/chunks")
async def get_knowledge_chunks(doc_id: str, current: int = 1, size: int = 10, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_page([], 0, current, size))


@router.post("/knowledge-base/docs/{doc_id}/chunks")
async def create_knowledge_chunk(doc_id: str, payload: dict[str, Any], _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"id": uuid4().hex[:16], "docId": doc_id, **payload})


@router.put("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}")
async def update_knowledge_chunk(
    doc_id: str,
    chunk_id: str,
    payload: dict[str, Any],
    _: JwtAuthorizationCredentials = Security(access_security),
):
    return success_result(data=None)


@router.delete("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}")
async def delete_knowledge_chunk(doc_id: str, chunk_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=None)


@router.patch("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}/enable")
async def enable_knowledge_chunk(doc_id: str, chunk_id: str, value: bool = True, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"docId": doc_id, "chunkId": chunk_id, "enabled": value})


@router.patch("/knowledge-base/docs/{doc_id}/chunks/batch-enable")
async def batch_enable_knowledge_chunks(doc_id: str, payload: dict[str, Any], value: bool = True, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"docId": doc_id, "chunkIds": payload.get("chunkIds", []), "enabled": value})


@router.get("/knowledge-base/docs/{doc_id}/preview")
async def preview_knowledge_document(
    doc_id: int,
    db: DbSession = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    row = db.get(KnowledgeBase, doc_id)
    return success_result(data=f"# {row.file_name}\n\nPreview is not available for migrated Swxy knowledge records." if row else "")


@router.get("/knowledge-base/docs/{doc_id}/chunk-logs")
async def get_chunk_logs(doc_id: str, current: int = 1, size: int = 10, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_page([], 0, current, size))


@router.get("/ingestion/pipelines")
async def get_ingestion_pipelines(pageNo: int = 1, pageSize: int = 10, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_page([], 0, pageNo, pageSize))


@router.get("/ingestion/pipelines/{pipeline_id}")
async def get_ingestion_pipeline(pipeline_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"id": pipeline_id, "name": pipeline_id, "nodes": []})


@router.post("/ingestion/pipelines")
async def create_ingestion_pipeline(payload: dict[str, Any], _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"id": uuid4().hex[:16], **payload, "nodes": payload.get("nodes", [])})


@router.put("/ingestion/pipelines/{pipeline_id}")
async def update_ingestion_pipeline(pipeline_id: str, payload: dict[str, Any], _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"id": pipeline_id, **payload, "nodes": payload.get("nodes", [])})


@router.delete("/ingestion/pipelines/{pipeline_id}")
async def delete_ingestion_pipeline(pipeline_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=pipeline_id)


@router.get("/ingestion/tasks")
async def get_ingestion_tasks(pageNo: int = 1, pageSize: int = 10, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_page([], 0, pageNo, pageSize))


@router.get("/ingestion/tasks/{task_id}")
async def get_ingestion_task(task_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"id": task_id, "pipelineId": "", "status": "success", "logs": []})


@router.get("/ingestion/tasks/{task_id}/nodes")
async def get_ingestion_task_nodes(task_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=[])


@router.post("/ingestion/tasks")
async def create_ingestion_task(payload: dict[str, Any], _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"taskId": uuid4().hex[:16], "pipelineId": payload.get("pipelineId"), "status": "success"})


@router.post("/ingestion/tasks/upload")
async def upload_ingestion_task(_: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"taskId": uuid4().hex[:16], "pipelineId": "", "status": "success"})


@router.get("/rag/traces/runs")
async def get_trace_runs(current: int = 1, size: int = 10, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_page([], 0, current, size))


@router.get("/rag/traces/runs/{trace_id}")
async def get_trace_detail(trace_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"run": {"traceId": trace_id, "status": "success"}, "nodes": []})


@router.get("/rag/traces/runs/{trace_id}/nodes")
async def get_trace_nodes(trace_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=[])


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
