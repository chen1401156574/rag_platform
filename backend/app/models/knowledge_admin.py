from sqlalchemy import Column, Integer, String, Text, DateTime, SmallInteger
from datetime import datetime
from models.base import Base


class KnowledgeBaseAdmin(Base):
    __tablename__ = 't_knowledge_base'

    id = Column(String(20), primary_key=True)
    name = Column(String(128), nullable=False)
    user_id = Column(String(64), nullable=False, index=True)
    embedding_model = Column(String(128), nullable=True)
    collection_name = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)
    document_count = Column(Integer, nullable=False, default=0)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    deleted = Column(SmallInteger, nullable=False, default=0)


class KnowledgeDocumentAdmin(Base):
    __tablename__ = 't_knowledge_document'

    id = Column(String(20), primary_key=True)
    kb_id = Column(String(20), nullable=False, index=True)
    doc_name = Column(String(255), nullable=False)
    source_type = Column(String(32), nullable=True, default='file')
    source_location = Column(String(512), nullable=True)
    file_type = Column(String(32), nullable=True)
    file_size = Column(Integer, nullable=True)
    file_url = Column(String(512), nullable=True)
    process_mode = Column(String(32), nullable=True, default='chunk')
    chunk_strategy = Column(String(64), nullable=True)
    chunk_config = Column(Text, nullable=True)
    pipeline_id = Column(String(20), nullable=True)
    status = Column(String(32), nullable=True, default='pending')
    enabled = Column(SmallInteger, nullable=False, default=1)
    chunk_count = Column(Integer, nullable=False, default=0)
    schedule_enabled = Column(SmallInteger, nullable=False, default=0)
    schedule_cron = Column(String(64), nullable=True)
    chunks_edited = Column(SmallInteger, nullable=False, default=0)
    created_by = Column(String(64), nullable=True)
    updated_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    deleted = Column(SmallInteger, nullable=False, default=0)
