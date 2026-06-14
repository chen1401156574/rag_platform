"""Phase 9: Dashboard — system overview KPIs + trend data."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.message import Message
from models.session import Session as ChatSession
from models.user import User
from service.auth import access_security
from utils.database import get_db
from utils.response import error_result, success_result

router = APIRouter()


def _window_hours(window: str) -> int:
    if window == "7d": return 168
    if window == "30d": return 720
    return 24


def _safe_count(db: Session, model, *filters) -> int:
    """Count rows for a model, returning 0 if the table doesn't exist."""
    try:
        q = select(func.count()).select_from(model)
        if filters:
            from sqlalchemy import and_
            q = q.where(and_(*filters))
        return db.scalar(q) or 0
    except Exception:
        return 0


def _safe_scalars(db: Session, query):
    """Execute a scalars query, returning empty list on error."""
    try:
        return db.scalars(query).all()
    except Exception:
        return []


@router.get("/admin/dashboard/overview")
async def get_dashboard_overview(
    window: str = "24h",
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    """系统核心指标大盘：用户数、知识库数、会话数、消息数"""
    try:
        # Core metrics from guaranteed tables (users, sessions, messages)
        total_users = _safe_count(db, User, User.deleted == 0)
        total_sessions = _safe_count(db, ChatSession)
        total_messages = _safe_count(db, Message)

        # Optional: knowledge base stats (tables may not exist yet)
        total_kbs = 0
        total_docs = 0
        try:
            from models.knowledge_admin import KnowledgeBaseAdmin, KnowledgeDocumentAdmin
            total_kbs = _safe_count(db, KnowledgeBaseAdmin, KnowledgeBaseAdmin.deleted == 0)
            total_docs = _safe_count(db, KnowledgeDocumentAdmin, KnowledgeDocumentAdmin.deleted == 0)
        except Exception:
            pass

        hours = _window_hours(window)
        since = datetime.now() - timedelta(hours=hours)
        sessions_window = _safe_count(db, ChatSession, ChatSession.created_at >= since)
        messages_window = _safe_count(db, Message, Message.create_time >= since)

        prev_since = datetime.now() - timedelta(hours=hours * 2)
        prev_messages = _safe_count(
            db, Message,
            Message.create_time >= prev_since,
            Message.create_time < since,
        )

        def delta(current: int, previous: int) -> dict:
            delta_val = current - previous
            delta_pct = round((delta_val / previous * 100), 1) if previous > 0 else (100.0 if current > 0 else 0.0)
            return {"value": current, "delta": delta_val, "deltaPct": delta_pct}

        return success_result(data={
            "window": window, "compareWindow": "previous",
            "updatedAt": int(datetime.now().timestamp() * 1000),
            "kpis": {
                "totalUsers": delta(total_users, total_users),
                "activeUsers": delta(total_users, total_users),
                "totalSessions": delta(total_sessions, total_sessions),
                "sessions24h": delta(sessions_window, 0),
                "totalMessages": delta(total_messages, prev_messages),
                "messages24h": delta(messages_window, 0),
            },
        })
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/admin/dashboard/performance")
async def get_dashboard_performance(
    window: str = "24h",
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    """性能指标：平均延迟、成功率、错误率"""
    try:
        avg_latency = 0
        p95 = 0
        success_rate = 100.0
        error_rate = 0.0

        # Try to get real data from trace table
        try:
            from models.trace import TraceRun
            hours = _window_hours(window)
            since = datetime.now() - timedelta(hours=hours)
            traces = _safe_scalars(
                db,
                select(TraceRun).where(TraceRun.start_time >= since, TraceRun.deleted == 0)
            )
            if traces:
                durations = [t.duration_ms for t in traces if t.duration_ms]
                errors = sum(1 for t in traces if t.status == "failed")
                avg_latency = sum(durations) // len(durations) if durations else 0
                sorted_d = sorted(durations)
                p95 = sorted_d[int(len(sorted_d) * 0.95)] if len(sorted_d) >= 20 else (sorted_d[-1] if sorted_d else 0)
                success_rate = round((len(traces) - errors) / len(traces) * 100, 2) if traces else 100.0
                error_rate = round(errors / len(traces) * 100, 2) if traces else 0.0
        except Exception:
            pass

        return success_result(data={
            "window": window,
            "avgLatencyMs": avg_latency,
            "p95LatencyMs": p95,
            "successRate": success_rate,
            "errorRate": error_rate,
            "noDocRate": 0,
            "slowRate": 0,
        })
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/admin/dashboard/trends")
async def get_dashboard_trends(
    metric: str,
    window: str = "7d",
    granularity: str = "day",
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    """每日对话波动趋势、请求平均响应时延趋势"""
    try:
        days = 7 if window == "7d" else (30 if window == "30d" else 7)
        now = datetime.now()
        points = []

        for i in range(days):
            day_start = datetime(now.year, now.month, now.day) - timedelta(days=days - 1 - i)
            day_end = day_start + timedelta(days=1)

            count = 0
            if metric in ("messages", "sessions"):
                model = Message if metric == "messages" else ChatSession
                col = Message.create_time if metric == "messages" else ChatSession.created_at
                count = _safe_count(db, model, col >= day_start, col < day_end)
            elif metric in ("latency", "avgLatency"):
                try:
                    from models.trace import TraceRun
                    day_traces = _safe_scalars(
                        db,
                        select(TraceRun).where(
                            TraceRun.start_time >= day_start,
                            TraceRun.start_time < day_end,
                            TraceRun.deleted == 0,
                        )
                    )
                    durs = [t.duration_ms for t in day_traces if t.duration_ms]
                    count = sum(durs) // len(durs) if durs else 0
                except Exception:
                    count = 0
            elif metric == "activeUsers":
                count = _safe_count(db, User, User.deleted == 0)
            else:
                count = 0

            points.append({"ts": int(day_start.timestamp() * 1000), "value": count})

        return success_result(data={
            "metric": metric, "window": window, "granularity": granularity,
            "series": [{"name": metric, "data": points}],
        })
    except Exception as e:
        return error_result(code="500", message=str(e))


# Plan-spec paths
@router.get("/dashboard/stats")
async def get_stats(
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    """实时聚合全系统核心元数据"""
    try:
        users = _safe_count(db, User, User.deleted == 0)
        messages = _safe_count(db, Message)
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_msgs = _safe_count(db, Message, Message.create_time >= yesterday)

        kbs = 0
        docs = 0
        try:
            from models.knowledge_admin import KnowledgeBaseAdmin, KnowledgeDocumentAdmin
            kbs = _safe_count(db, KnowledgeBaseAdmin, KnowledgeBaseAdmin.deleted == 0)
            docs = _safe_count(db, KnowledgeDocumentAdmin, KnowledgeDocumentAdmin.deleted == 0)
        except Exception:
            pass

        return success_result(data={
            "totalUsers": users, "totalKnowledgeBases": kbs, "totalDocuments": docs,
            "totalMessages": messages, "yesterdayMessages": yesterday_msgs,
        })
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/dashboard/trend")
async def get_trend(
    metric: str = "messages",
    window: str = "7d",
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    """以天为单位返回趋势数据"""
    try:
        days = 7 if window == "7d" else 30
        now = datetime.now()
        points = []
        for i in range(days):
            day_start = datetime(now.year, now.month, now.day) - timedelta(days=days - 1 - i)
            day_end = day_start + timedelta(days=1)
            count = 0
            if metric == "messages":
                count = _safe_count(db, Message, Message.create_time >= day_start, Message.create_time < day_end)
            points.append({"date": day_start.strftime("%Y-%m-%d"), "value": count})
        return success_result(data={"metric": metric, "window": window, "points": points})
    except Exception as e:
        return error_result(code="500", message=str(e))
