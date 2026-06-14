from sqlalchemy import Column, Integer, String, Text, DateTime, SmallInteger, BigInteger
from datetime import datetime
from models.base import Base


class IngestionPipeline(Base):
    __tablename__ = 't_ingestion_pipeline'

    id = Column(String(20), primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    nodes_json = Column(Text, nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    deleted = Column(SmallInteger, nullable=False, default=0)


class IngestionTask(Base):
    __tablename__ = 't_ingestion_task'

    id = Column(String(20), primary_key=True)
    pipeline_id = Column(String(20), nullable=False, index=True)
    source_type = Column(String(32), nullable=True)
    source_location = Column(String(512), nullable=True)
    source_file_name = Column(String(255), nullable=True)
    status = Column(String(32), nullable=True, default='pending')
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, nullable=True, default=0)
    logs_json = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    deleted = Column(SmallInteger, nullable=False, default=0)


class IngestionTaskNode(Base):
    __tablename__ = 't_ingestion_task_node'

    id = Column(String(20), primary_key=True)
    task_id = Column(String(20), nullable=False, index=True)
    pipeline_id = Column(String(20), nullable=True)
    node_id = Column(String(64), nullable=True)
    node_type = Column(String(32), nullable=True)
    node_order = Column(Integer, nullable=True)
    status = Column(String(32), nullable=True, default='pending')
    duration_ms = Column(Integer, nullable=True)
    message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class IngestionChunkLog(Base):
    """切片入库耗时日志表 — Plan Phase 7"""
    __tablename__ = 't_knowledge_document_chunk_log'

    id = Column(String(20), primary_key=True)
    doc_id = Column(String(20), nullable=False, index=True)
    status = Column(String(32), nullable=True, default='pending')
    process_mode = Column(String(32), nullable=True)
    chunk_strategy = Column(String(64), nullable=True)
    pipeline_id = Column(String(20), nullable=True)
    pipeline_name = Column(String(128), nullable=True)
    extract_duration = Column(Integer, nullable=True)
    chunk_duration = Column(Integer, nullable=True)
    embed_duration = Column(Integer, nullable=True)
    persist_duration = Column(Integer, nullable=True)
    other_duration = Column(Integer, nullable=True)
    total_duration = Column(Integer, nullable=True)
    chunk_count = Column(Integer, nullable=True, default=0)
    error_message = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
