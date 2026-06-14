"""Phase 8: Link Tracing - trace run list/detail and conversation aggregation."""
import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from models.session import Session as ChatSession
from models.trace import TraceRun, TraceNode
from models.user import User
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


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    normalized = normalized.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def _parse_bool(value: Optional[bool | str]) -> Optional[bool]:
    if value is None or isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _parse_status_filter(value: Optional[str]) -> set[str]:
    if not value:
        return set()
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def _normalize_status(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _aggregate_status(statuses: list[Optional[str]]) -> str:
    normalized = {_normalize_status(status) for status in statuses if _normalize_status(status)}
    if "failed" in normalized or "timeout" in normalized:
        return "failed"
    if "running" in normalized:
        return "running"
    if "clarify_needed" in normalized:
        return "clarify_needed"
    if "success" in normalized:
        return "success"
    return "unknown"


def _safe_avg(values: list[Optional[int]]) -> Optional[int]:
    numeric = [int(value) for value in values if isinstance(value, int)]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric))


def _safe_max(values: list[Optional[int]]) -> Optional[int]:
    numeric = [int(value) for value in values if isinstance(value, int)]
    return max(numeric) if numeric else None


def _run_sort_key(run: TraceRun) -> tuple[datetime, datetime]:
    min_dt = datetime.min
    return (run.start_time or run.created_at or min_dt, run.created_at or min_dt)


def _run_record(r: TraceRun) -> dict:
    return {
        "traceId": r.trace_id,
        "traceName": r.trace_name,
        "entryMethod": r.entry_method,
        "conversationId": r.conversation_id,
        "sessionId": r.conversation_id,
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
        "intentCode": None,
        "intentName": None,
        "intentScore": None,
    }


def _extract_intent(output_json: Optional[str]) -> Optional[dict]:
    try:
        output = json.loads(output_json) if output_json else {}
    except (json.JSONDecodeError, TypeError):
        output = {}
    data = output.get("data") if isinstance(output, dict) else None
    if isinstance(data, dict):
        output = data
    if not isinstance(output, dict) or not output.get("intent_code"):
        return None
    return {
        "intentCode": output.get("intent_code"),
        "intentName": output.get("name") or output.get("intent_code"),
        "intentScore": output.get("score"),
    }


def _extract_final_answer(output_json: Optional[str]) -> Optional[str]:
    try:
        output = json.loads(output_json) if output_json else {}
    except (json.JSONDecodeError, TypeError):
        return None
    data = output.get("data") if isinstance(output, dict) else None
    if isinstance(data, dict):
        output = data
    if not isinstance(output, dict):
        return None
    summary = output.get("answer_summary") or output.get("summary") or output.get("answer")
    if not summary:
        return None
    text = str(summary).strip()
    return text[:260] + "..." if len(text) > 260 else text


def _load_trace_node_summary(db: Session, trace_ids: list[str]) -> tuple[dict[str, dict], dict[str, dict]]:
    if not trace_ids:
        return {}, {}
    nodes = db.scalars(
        select(TraceNode)
        .where(TraceNode.trace_id.in_(trace_ids))
        .order_by(TraceNode.trace_id.asc(), TraceNode.start_time.asc().nullslast(), TraceNode.created_at.asc())
    ).all()
    intent_map: dict[str, dict] = {}
    stats: dict[str, dict] = defaultdict(lambda: {
        "nodeCount": 0,
        "failedNodeCount": 0,
        "hasClarify": False,
        "finalAnswerSummary": None,
        "persisted": None,
    })
    for node in nodes:
        trace_stats = stats[node.trace_id]
        trace_stats["nodeCount"] += 1
        if _normalize_status(node.status) in {"failed", "timeout"}:
            trace_stats["failedNodeCount"] += 1
        if node.node_type in {"ClarifyResponse", "ClarificationMerge"}:
            trace_stats["hasClarify"] = True
        if node.node_type == "IntentClassify":
            intent = _extract_intent(node.output_json)
            if intent:
                intent_map[node.trace_id] = intent
        if node.node_type == "LLMFinalAnswer":
            summary = _extract_final_answer(node.output_json)
            if summary:
                trace_stats["finalAnswerSummary"] = summary
        if node.node_type == "PersistMessage":
            trace_stats["persisted"] = _normalize_status(node.status) not in {"failed", "timeout"}
    return intent_map, stats


def _enrich_intents(db: Session, runs: list[dict]) -> None:
    """从 IntentClassify 节点批量提取意图信息，回填到 run 记录中"""
    if not runs:
        return
    trace_ids = [r["traceId"] for r in runs]
    intent_map, _ = _load_trace_node_summary(db, trace_ids)
    for r in runs:
        intent = intent_map.get(r["traceId"])
        if intent:
            r["intentCode"] = intent["intentCode"]
            r["intentName"] = intent["intentName"]
            r["intentScore"] = intent["intentScore"]


def _session_user_maps(db: Session, session_ids: list[str], user_ids: list[str]) -> tuple[dict[str, Any], dict[str, str]]:
    sessions: dict[str, Any] = {}
    users: dict[str, str] = {}
    if session_ids:
        session_rows = db.scalars(select(ChatSession).where(ChatSession.session_id.in_(session_ids))).all()
        sessions = {row.session_id: row for row in session_rows}
        user_ids = list({*user_ids, *(str(row.user_id) for row in session_rows if row.user_id)})
    int_user_ids = [int(uid) for uid in set(user_ids) if str(uid).isdigit()]
    if int_user_ids:
        user_rows = db.scalars(select(User).where(User.id.in_(int_user_ids), User.deleted == 0)).all()
        users = {str(row.id): row.username for row in user_rows}
    return sessions, users


def _conversation_record(
    session_id: str,
    runs: list[TraceRun],
    intent_map: dict[str, dict],
    node_stats: dict[str, dict],
    sessions: dict[str, Any],
    users: dict[str, str],
) -> dict:
    ordered = sorted(runs, key=_run_sort_key)
    first_run = ordered[0]
    last_run = ordered[-1]
    session = sessions.get(session_id)
    last_intent = intent_map.get(last_run.trace_id)
    if not last_intent:
        for run in reversed(ordered):
            last_intent = intent_map.get(run.trace_id)
            if last_intent:
                break

    statuses = [run.status for run in ordered]
    failed_node_count = sum((node_stats.get(run.trace_id) or {}).get("failedNodeCount", 0) for run in ordered)
    has_clarify = any(
        _normalize_status(run.status) == "clarify_needed"
        or bool((node_stats.get(run.trace_id) or {}).get("hasClarify"))
        for run in ordered
    )
    user_id = str(last_run.user_id or getattr(session, "user_id", "") or "")
    user_name = last_run.user_name or users.get(user_id)
    return {
        "sessionId": session_id,
        "conversationId": session_id,
        "sessionName": getattr(session, "session_name", None),
        "userId": user_id or None,
        "userName": user_name,
        "turnCount": len(ordered),
        "successCount": sum(1 for run in ordered if _normalize_status(run.status) == "success"),
        "failedCount": sum(1 for run in ordered if _normalize_status(run.status) in {"failed", "timeout"}),
        "runningCount": sum(1 for run in ordered if _normalize_status(run.status) == "running"),
        "clarifyCount": sum(1 for run in ordered if _normalize_status(run.status) == "clarify_needed"),
        "failedNodeCount": failed_node_count,
        "hasFailedNode": failed_node_count > 0,
        "hasClarify": has_clarify,
        "lastTraceId": last_run.trace_id,
        "lastQuestion": last_run.question,
        "lastIntentCode": (last_intent or {}).get("intentCode"),
        "lastIntentName": (last_intent or {}).get("intentName"),
        "lastIntentScore": (last_intent or {}).get("intentScore"),
        "lastStatus": last_run.status,
        "status": _aggregate_status(statuses),
        "avgDurationMs": _safe_avg([run.duration_ms for run in ordered]),
        "avgTtftMs": _safe_avg([run.ttft_ms for run in ordered]),
        "maxDurationMs": _safe_max([run.duration_ms for run in ordered]),
        "firstStartTime": _dt(first_run.start_time),
        "lastStartTime": _dt(last_run.start_time),
        "lastEndTime": _dt(last_run.end_time),
    }


def _conversation_run_record(
    run: TraceRun,
    turn_no: int,
    intent_map: dict[str, dict],
    node_stats: dict[str, dict],
) -> dict:
    intent = intent_map.get(run.trace_id) or {}
    stats = node_stats.get(run.trace_id) or {}
    return {
        **_run_record(run),
        "turnNo": turn_no,
        "intentCode": intent.get("intentCode"),
        "intentName": intent.get("intentName"),
        "intentScore": intent.get("intentScore"),
        "nodeCount": stats.get("nodeCount", 0),
        "failedNodeCount": stats.get("failedNodeCount", 0),
        "hasClarify": bool(stats.get("hasClarify") or _normalize_status(run.status) == "clarify_needed"),
        "finalAnswerSummary": stats.get("finalAnswerSummary"),
        "persisted": stats.get("persisted"),
    }


def _trace_time_filter(column, fallback_column, start_dt: Optional[datetime], end_dt: Optional[datetime]) -> list[Any]:
    filters: list[Any] = []
    if start_dt:
        filters.append(or_(column >= start_dt, and_(column.is_(None), fallback_column >= start_dt)))
    if end_dt:
        filters.append(or_(column <= end_dt, and_(column.is_(None), fallback_column <= end_dt)))
    return filters


def _passes_numeric_range(value: Optional[int], minimum: Optional[int], maximum: Optional[int]) -> bool:
    if minimum is not None and (value is None or value < minimum):
        return False
    if maximum is not None and (value is None or value > maximum):
        return False
    return True


def _node_record(n: TraceNode) -> dict:
    return {
        "traceId": getattr(n, "trace_id", None),
        "nodeId": getattr(n, "node_id", None),
        "parentNodeId": getattr(n, "parent_node_id", None),
        "depth": getattr(n, "depth", None),
        "nodeType": getattr(n, "node_type", None),
        "nodeName": getattr(n, "node_name", None),
        "className": getattr(n, "class_name", None),
        "methodName": getattr(n, "method_name", None),
        "status": getattr(n, "status", None),
        "errorMessage": getattr(n, "error_message", None),
        "durationMs": getattr(n, "duration_ms", None),
        "startTime": _dt(getattr(n, "start_time", None)),
        "endTime": _dt(getattr(n, "end_time", None)),
        "inputJson": getattr(n, "input_json", None),
        "outputJson": getattr(n, "output_json", None),
        "extraData": getattr(n, "extra_data_json", None),
    }


@router.get("/rag/traces/conversations")
async def list_trace_conversations(
    current: int = 1,
    size: int = 10,
    sessionId: Optional[str] = None,
    traceId: Optional[str] = None,
    userName: Optional[str] = None,
    userId: Optional[str] = None,
    status: Optional[str] = None,
    intentCode: Optional[str] = None,
    keyword: Optional[str] = None,
    minDurationMs: Optional[int] = None,
    maxDurationMs: Optional[int] = None,
    minTtftMs: Optional[int] = None,
    maxTtftMs: Optional[int] = None,
    hasFailedNode: Optional[bool | str] = None,
    hasClarify: Optional[bool | str] = None,
    startTime: Optional[str] = None,
    endTime: Optional[str] = None,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        page = max(current, 1)
        page_size = max(size, 1)

        trace_session_ids: Optional[list[str]] = None
        if traceId and traceId.strip():
            matched_session_ids = db.scalars(
                select(TraceRun.conversation_id)
                .where(
                    TraceRun.deleted == 0,
                    TraceRun.trace_id.ilike(f"%{traceId.strip()}%"),
                    TraceRun.conversation_id.isnot(None),
                    TraceRun.conversation_id != "",
                )
            ).all()
            trace_session_ids = sorted({sid for sid in matched_session_ids if sid})
            if not trace_session_ids:
                return success_result(data=_page([], 0, page, page_size))

        filters: list[Any] = [
            TraceRun.deleted == 0,
            TraceRun.conversation_id.isnot(None),
            TraceRun.conversation_id != "",
        ]
        if trace_session_ids is not None:
            filters.append(TraceRun.conversation_id.in_(trace_session_ids))
        if sessionId and sessionId.strip():
            filters.append(TraceRun.conversation_id.ilike(f"%{sessionId.strip()}%"))
        if keyword and keyword.strip():
            filters.append(TraceRun.question.ilike(f"%{keyword.strip()}%"))

        start_dt = _parse_dt(startTime)
        end_dt = _parse_dt(endTime)
        if not start_dt and not sessionId and not traceId:
            start_dt = datetime.now() - timedelta(hours=24)
        filters.extend(_trace_time_filter(TraceRun.start_time, TraceRun.created_at, start_dt, end_dt))

        rows = db.scalars(
            select(TraceRun)
            .where(and_(*filters))
            .order_by(TraceRun.start_time.desc().nullslast(), TraceRun.created_at.desc())
        ).all()
        if not rows:
            return success_result(data=_page([], 0, page, page_size))

        groups: dict[str, list[TraceRun]] = defaultdict(list)
        for run in rows:
            if run.conversation_id:
                groups[run.conversation_id].append(run)

        trace_ids = [run.trace_id for run in rows]
        intent_map, node_stats = _load_trace_node_summary(db, trace_ids)
        sessions, users = _session_user_maps(
            db,
            list(groups.keys()),
            [str(run.user_id) for run in rows if run.user_id],
        )

        status_filter = _parse_status_filter(status)
        failed_filter = _parse_bool(hasFailedNode)
        clarify_filter = _parse_bool(hasClarify)
        normalized_intent = (intentCode or "").strip()
        normalized_user_name = (userName or "").strip().lower()
        normalized_user_id = (userId or "").strip()

        records: list[dict] = []
        for session_id, session_runs in groups.items():
            record = _conversation_record(session_id, session_runs, intent_map, node_stats, sessions, users)

            if status_filter and _normalize_status(record.get("status")) not in status_filter:
                continue
            if normalized_user_id and str(record.get("userId") or "") != normalized_user_id:
                continue
            if normalized_user_name and normalized_user_name not in str(record.get("userName") or "").lower():
                continue
            if normalized_intent and not any(
                (intent_map.get(run.trace_id) or {}).get("intentCode") == normalized_intent
                for run in session_runs
            ):
                continue
            if failed_filter is not None and bool(record.get("hasFailedNode")) != failed_filter:
                continue
            if clarify_filter is not None and bool(record.get("hasClarify")) != clarify_filter:
                continue
            if not _passes_numeric_range(record.get("maxDurationMs"), minDurationMs, maxDurationMs):
                continue
            if not _passes_numeric_range(record.get("avgTtftMs"), minTtftMs, maxTtftMs):
                continue

            records.append(record)

        records.sort(key=lambda item: item.get("lastStartTime") or item.get("lastEndTime") or "", reverse=True)
        total = len(records)
        offset = (page - 1) * page_size
        return success_result(data=_page(records[offset:offset + page_size], total, page, page_size))
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/rag/traces/conversations/{session_id}")
async def get_trace_conversation_detail(
    session_id: str,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        runs = db.scalars(
            select(TraceRun)
            .where(TraceRun.deleted == 0, TraceRun.conversation_id == session_id)
            .order_by(TraceRun.start_time.asc().nullslast(), TraceRun.created_at.asc())
        ).all()
        if not runs:
            return error_result(code="404", message="Conversation not found")

        trace_ids = [run.trace_id for run in runs]
        intent_map, node_stats = _load_trace_node_summary(db, trace_ids)
        sessions, users = _session_user_maps(
            db,
            [session_id],
            [str(run.user_id) for run in runs if run.user_id],
        )
        conversation = _conversation_record(session_id, runs, intent_map, node_stats, sessions, users)
        ordered = sorted(runs, key=_run_sort_key)
        return success_result(data={
            "conversation": conversation,
            "runs": [
                _conversation_run_record(run, index + 1, intent_map, node_stats)
                for index, run in enumerate(ordered)
            ],
        })
    except Exception as e:
        return error_result(code="500", message=str(e))


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
        run_records = [_run_record(r) for r in rows]
        _enrich_intents(db, run_records)
        return success_result(data=_page(run_records, total, page, page_size))
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

        run_record = _run_record(run)
        _enrich_intents(db, [run_record])

        return success_result(data={
            "run": run_record,
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
