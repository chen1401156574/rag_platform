from sqlalchemy import Column, Integer, String, Text, DateTime, SmallInteger
from datetime import datetime
from models.base import Base


class TraceRun(Base):
    """链路追踪会话大表 — Plan Phase 8"""
    __tablename__ = 't_rag_trace_run'

    id = Column(String(20), primary_key=True)
    trace_id = Column(String(40), nullable=False, unique=True, index=True)
    trace_name = Column(String(255), nullable=True)
    entry_method = Column(String(64), nullable=True)
    conversation_id = Column(String(40), nullable=True, index=True)
    task_id = Column(String(40), nullable=True)
    user_name = Column(String(64), nullable=True)
    user_id = Column(String(64), nullable=True)
    status = Column(String(32), nullable=True, default='running')
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    ttft_ms = Column(Integer, nullable=True)
    question = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    deleted = Column(SmallInteger, nullable=False, default=0)


class TraceNode(Base):
    """链路追踪算子节点表 — Plan Phase 8"""
    __tablename__ = 't_rag_trace_node'

    id = Column(String(20), primary_key=True)
    trace_id = Column(String(40), nullable=False, index=True)
    node_id = Column(String(64), nullable=False)
    parent_node_id = Column(String(64), nullable=True)
    depth = Column(Integer, nullable=True, default=0)
    node_type = Column(String(32), nullable=True)
    node_name = Column(String(128), nullable=True)
    class_name = Column(String(128), nullable=True)
    method_name = Column(String(128), nullable=True)
    status = Column(String(32), nullable=True, default='running')
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    input_json = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    extra_data_json = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
