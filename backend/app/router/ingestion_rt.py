"""Phase 7: Ingestion Monitoring — pipeline/task management + stats + queue."""
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, Security, UploadFile
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from models.ingestion import IngestionChunkLog, IngestionPipeline, IngestionTask, IngestionTaskNode
from service.auth import access_security
from utils.database import get_db
from utils.response import error_result, success_result

router = APIRouter()


def _uid() -> str:
    return str(uuid.uuid4()).replace("-", "")[:20]


def _page(records: list[dict], total: int, current: int = 1, size: int = 10) -> dict:
    ps = max(size, 1)
    return {"records": records, "total": total, "size": size, "current": current, "pages": (total + ps - 1) // ps}


def _dt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


# ── Pipeline CRUD ──

def _pipeline_record(p: IngestionPipeline) -> dict:
    nodes = []
    if p.nodes_json:
        try:
            nodes = json.loads(p.nodes_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "createdBy": p.created_by, "nodes": nodes,
        "createTime": _dt(p.created_at), "updateTime": _dt(p.updated_at),
    }


@router.get("/ingestion/pipelines")
async def list_pipelines(
    pageNo: int = 1, pageSize: int = 10, keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        filters = [IngestionPipeline.deleted == 0]
        if keyword:
            filters.append(IngestionPipeline.name.ilike(f"%{keyword}%"))
        total = db.scalar(select(func.count()).select_from(IngestionPipeline).where(and_(*filters))) or 0
        rows = db.scalars(
            select(IngestionPipeline).where(and_(*filters))
            .order_by(IngestionPipeline.updated_at.desc())
            .offset((pageNo - 1) * pageSize).limit(pageSize)
        ).all()
        return success_result(data=_page([_pipeline_record(r) for r in rows], total, pageNo, pageSize))
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/ingestion/pipelines/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str, db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        p = db.scalars(select(IngestionPipeline).where(IngestionPipeline.id == pipeline_id, IngestionPipeline.deleted == 0)).first()
        return success_result(data=_pipeline_record(p) if p else {"id": pipeline_id, "name": pipeline_id, "nodes": []})
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.post("/ingestion/pipelines")
async def create_pipeline(
    payload: dict[str, Any], db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        username = credentials.subject.get("user_name", "admin")
        p = IngestionPipeline(
            id=_uid(), name=payload.get("name", ""), description=payload.get("description"),
            nodes_json=json.dumps(payload.get("nodes", []), ensure_ascii=False) if payload.get("nodes") else None,
            created_by=username,
        )
        db.add(p); db.commit()
        return success_result(data={"id": p.id, **payload, "nodes": payload.get("nodes", [])})
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.put("/ingestion/pipelines/{pipeline_id}")
async def update_pipeline(
    pipeline_id: str, payload: dict[str, Any], db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        p = db.scalars(select(IngestionPipeline).where(IngestionPipeline.id == pipeline_id, IngestionPipeline.deleted == 0)).first()
        if not p:
            return error_result(code="404", message="流水线不存在")
        if "name" in payload: p.name = payload["name"]
        if "description" in payload: p.description = payload.get("description")
        if "nodes" in payload: p.nodes_json = json.dumps(payload["nodes"], ensure_ascii=False)
        p.updated_at = datetime.now(); db.commit()
        return success_result(data={"id": pipeline_id, **payload, "nodes": payload.get("nodes", [])})
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.delete("/ingestion/pipelines/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: str, db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        p = db.scalars(select(IngestionPipeline).where(IngestionPipeline.id == pipeline_id, IngestionPipeline.deleted == 0)).first()
        if p: p.deleted = 1; db.commit()
        return success_result(data=pipeline_id)
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


# ── Task CRUD ──

def _task_record(t: IngestionTask) -> dict:
    logs = []
    if t.logs_json:
        try: logs = json.loads(t.logs_json)
        except (json.JSONDecodeError, TypeError): pass
    metadata = None
    if t.metadata_json:
        try: metadata = json.loads(t.metadata_json)
        except (json.JSONDecodeError, TypeError): pass
    return {
        "id": t.id, "pipelineId": t.pipeline_id, "sourceType": t.source_type,
        "sourceLocation": t.source_location, "sourceFileName": t.source_file_name,
        "status": t.status, "chunkCount": t.chunk_count, "errorMessage": t.error_message,
        "logs": logs, "metadata": metadata,
        "startedAt": _dt(t.started_at), "completedAt": _dt(t.completed_at),
        "createdBy": t.created_by, "createTime": _dt(t.created_at), "updateTime": _dt(t.updated_at),
    }


@router.get("/ingestion/tasks")
async def list_tasks(
    pageNo: int = 1, pageSize: int = 10, status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        filters = [IngestionTask.deleted == 0]
        if status: filters.append(IngestionTask.status == status)
        total = db.scalar(select(func.count()).select_from(IngestionTask).where(and_(*filters))) or 0
        rows = db.scalars(
            select(IngestionTask).where(and_(*filters))
            .order_by(IngestionTask.created_at.desc())
            .offset((pageNo - 1) * pageSize).limit(pageSize)
        ).all()
        return success_result(data=_page([_task_record(r) for r in rows], total, pageNo, pageSize))
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/ingestion/tasks/{task_id}")
async def get_task(
    task_id: str, db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        t = db.scalars(select(IngestionTask).where(IngestionTask.id == task_id, IngestionTask.deleted == 0)).first()
        return success_result(data=_task_record(t) if t else {"id": task_id, "pipelineId": "", "status": "success", "logs": []})
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/ingestion/tasks/{task_id}/nodes")
async def get_task_nodes(
    task_id: str, db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        rows = db.scalars(
            select(IngestionTaskNode).where(IngestionTaskNode.task_id == task_id).order_by(IngestionTaskNode.node_order.asc())
        ).all()
        records = [
            {
                "id": n.id, "taskId": n.task_id, "pipelineId": n.pipeline_id,
                "nodeId": n.node_id, "nodeType": n.node_type, "nodeOrder": n.node_order,
                "status": n.status, "durationMs": n.duration_ms, "message": n.message,
                "errorMessage": n.error_message,
                "output": json.loads(n.output_json) if n.output_json else None,
                "createTime": _dt(n.created_at), "updateTime": _dt(n.created_at),
            }
            for n in rows
        ]
        return success_result(data=records)
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.post("/ingestion/tasks")
async def create_task(
    payload: dict[str, Any], db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        username = credentials.subject.get("user_name", "admin")
        t = IngestionTask(
            id=_uid(), pipeline_id=payload.get("pipelineId", ""),
            source_type=payload.get("source", {}).get("type") if isinstance(payload.get("source"), dict) else None,
            source_location=payload.get("source", {}).get("location") if isinstance(payload.get("source"), dict) else None,
            source_file_name=payload.get("source", {}).get("fileName") if isinstance(payload.get("source"), dict) else None,
            metadata_json=json.dumps(payload.get("metadata"), ensure_ascii=False) if payload.get("metadata") else None,
            status="success", created_by=username,
        )
        db.add(t); db.commit()
        return success_result(data={"taskId": t.id, "pipelineId": t.pipeline_id, "status": t.status})
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.post("/ingestion/tasks/upload")
async def upload_task(
    pipelineId: Optional[str] = Form(None), file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        username = credentials.subject.get("user_name", "admin")
        t = IngestionTask(
            id=_uid(), pipeline_id=pipelineId or "", source_type="file",
            source_file_name=file.filename if file else "unknown",
            status="success", created_by=username,
        )
        db.add(t); db.commit()
        return success_result(data={"taskId": t.id, "pipelineId": t.pipeline_id, "status": t.status})
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


# ── Ingestion Stats & Queue (Plan Phase 7 core deliverables) ──

@router.get("/ingestion/stats")
async def get_ingestion_stats(
    windows: str = "24h",
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    """聚合获取解析成功的文档数、失败数、平均处理耗时"""
    try:
        hours = 24
        if windows == "7d": hours = 168
        elif windows == "30d": hours = 720
        since = datetime.now() - timedelta(hours=hours)

        all_logs = db.scalars(
            select(IngestionChunkLog).where(IngestionChunkLog.created_at >= since)
        ).all()

        success = sum(1 for l in all_logs if l.status == "success")
        failed = sum(1 for l in all_logs if l.status == "failed")
        running = sum(1 for l in all_logs if l.status == "running")
        durations = [l.total_duration for l in all_logs if l.total_duration]
        avg_duration = sum(durations) // len(durations) if durations else 0
        total_chunks = sum(l.chunk_count or 0 for l in all_logs)

        return success_result(data={
            "window": windows,
            "totalTasks": len(all_logs),
            "successCount": success,
            "failedCount": failed,
            "runningCount": running,
            "avgDurationMs": avg_duration,
            "totalChunks": total_chunks,
        })
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/ingestion/queue")
async def get_ingestion_queue(
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    """展示当前后台正在排队等待解析的文档队列及状态"""
    try:
        rows = db.scalars(
            select(IngestionTask)
            .where(IngestionTask.deleted == 0, IngestionTask.status.in_(["pending", "running"]))
            .order_by(IngestionTask.status.desc(), IngestionTask.created_at.asc())
            .limit(50)
        ).all()
        return success_result(data={
            "total": len(rows),
            "items": [_task_record(r) for r in rows],
        })
    except Exception as e:
        return error_result(code="500", message=str(e))
