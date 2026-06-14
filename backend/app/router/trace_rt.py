"""Phase 8: Link Tracing — trace run list + detail with node tree."""
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from models.trace import TraceRun, TraceNode
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
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return str(value)


def _run_record(r: TraceRun) -> dict:
    return {
        "traceId": r.trace_id,
        "traceName": r.trace_name,
        "entryMethod": r.entry_method,
        "conversationId": r.conversation_id,
        "taskId": r.task_id,
        "userName": r.user_name,
        "username": r.user_name,
        "userId": r.user_id,
        "status": r.status,
        "errorMessage": r.error_message,
        "durationMs": r.duration_ms,
        "ttftMs": r.ttft_ms,
        "question": r.question,
        "startTime": _dt(r.start_time),
        "endTime": _dt(r.end_time),
    }


def _node_record(n: TraceNode) -> dict:
    return {
        "traceId": n.trace_id,
        "nodeId": n.node_id,
        "parentNodeId": n.parent_node_id,
        "depth": n.depth,
        "nodeType": n.node_type,
        "nodeName": n.node_name,
        "className": n.class_name,
        "methodName": n.method_name,
        "status": n.status,
        "errorMessage": n.error_message,
        "durationMs": n.duration_ms,
        "startTime": _dt(n.start_time),
        "endTime": _dt(n.end_time),
        "extraData": n.extra_data_json,
    }


@router.get("/rag/traces/runs")
@router.get("/trace/page")
async def list_traces(
    current: int = 1, size: int = 10,
    traceId: Optional[str] = None,
    conversationId: Optional[str] = None,
    taskId: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        page = max(current, 1)
        page_size = max(size, 1)
        filters = [TraceRun.deleted == 0]
        if traceId: filters.append(TraceRun.trace_id.ilike(f"%{traceId}%"))
        if conversationId: filters.append(TraceRun.conversation_id == conversationId)
        if taskId: filters.append(TraceRun.task_id == taskId)
        if status: filters.append(TraceRun.status == status)

        total = db.scalar(select(func.count()).select_from(TraceRun).where(and_(*filters))) or 0
        rows = db.scalars(
            select(TraceRun).where(and_(*filters))
            .order_by(TraceRun.start_time.desc().nullslast(), TraceRun.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return success_result(data=_page([_run_record(r) for r in rows], total, page, page_size))
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/rag/traces/runs/{trace_id}")
@router.get("/trace/{trace_id}/detail")
async def get_trace_detail(
    trace_id: str,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        run = db.scalars(select(TraceRun).where(TraceRun.trace_id == trace_id, TraceRun.deleted == 0)).first()
        if not run:
            return error_result(code="404", message="Trace not found")

        nodes = db.scalars(
            select(TraceNode).where(TraceNode.trace_id == trace_id)
            .order_by(TraceNode.depth.asc(), TraceNode.start_time.asc())
        ).all()

        return success_result(data={
            "run": _run_record(run),
            "nodes": [_node_record(n) for n in nodes],
        })
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/rag/traces/runs/{trace_id}/nodes")
async def get_trace_nodes(
    trace_id: str,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        nodes = db.scalars(
            select(TraceNode).where(TraceNode.trace_id == trace_id)
            .order_by(TraceNode.depth.asc(), TraceNode.start_time.asc())
        ).all()
        return success_result(data=[_node_record(n) for n in nodes])
    except Exception as e:
        return error_result(code="500", message=str(e))


# ── Write-back helper (used by chat_rt interceptor) ──

@router.post("/rag/traces/runs")
async def create_trace_run(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    """Record a new trace run (called by chat_rt interceptor)."""
    try:
        trace_id = payload.get("traceId") or _uid()
        run = TraceRun(
            id=_uid(), trace_id=trace_id,
            trace_name=payload.get("traceName"),
            entry_method=payload.get("entryMethod", "chat"),
            conversation_id=payload.get("conversationId"),
            task_id=payload.get("taskId"),
            user_name=payload.get("userName"),
            user_id=payload.get("userId"),
            question=payload.get("question"),
            status=payload.get("status", "running"),
            start_time=datetime.now(),
        )
        db.add(run); db.commit()
        return success_result(data=trace_id)
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.post("/rag/traces/runs/{trace_id}/nodes")
async def add_trace_node(
    trace_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    """Record a trace node (called by chat_rt interceptor)."""
    try:
        node = TraceNode(
            id=_uid(), trace_id=trace_id,
            node_id=payload.get("nodeId", _uid()),
            parent_node_id=payload.get("parentNodeId"),
            depth=payload.get("depth", 0),
            node_type=payload.get("nodeType"),
            node_name=payload.get("nodeName"),
            class_name=payload.get("className"),
            method_name=payload.get("methodName"),
            status=payload.get("status", "success"),
            error_message=payload.get("errorMessage"),
            duration_ms=payload.get("durationMs"),
            input_json=json.dumps(payload.get("input"), ensure_ascii=False) if payload.get("input") else None,
            output_json=json.dumps(payload.get("output"), ensure_ascii=False) if payload.get("output") else None,
            extra_data_json=json.dumps(payload.get("extraData"), ensure_ascii=False) if payload.get("extraData") else None,
            start_time=datetime.now(),
            end_time=datetime.now(),
        )
        db.add(node); db.commit()
        return success_result(data=node.node_id)
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.patch("/rag/traces/runs/{trace_id}")
async def finish_trace_run(
    trace_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    """Mark a trace run as completed/failed."""
    try:
        run = db.scalars(select(TraceRun).where(TraceRun.trace_id == trace_id)).first()
        if run:
            if "status" in payload: run.status = payload["status"]
            if "durationMs" in payload: run.duration_ms = payload["durationMs"]
            if "ttftMs" in payload: run.ttft_ms = payload["ttftMs"]
            if "errorMessage" in payload: run.error_message = payload["errorMessage"]
            run.end_time = datetime.now()
            db.commit()
        return success_result(data=trace_id)
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))
