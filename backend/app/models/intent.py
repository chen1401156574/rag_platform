from sqlalchemy import Column, Integer, String, Text, DateTime, SmallInteger
from datetime import datetime
from models.base import Base

class IntentNode(Base):
    __tablename__ = 't_intent_node'

    id = Column(String(20), primary_key=True)
    kb_id = Column(String(20), nullable=True)
    intent_code = Column(String(64), nullable=False)
    name = Column(String(64), nullable=False)
    level = Column(SmallInteger, nullable=False)
    parent_code = Column(String(64), nullable=True)
    description = Column(String(512), nullable=True)
    examples = Column(Text, nullable=True)  # JSON 数组字符串
    collection_name = Column(String(128), nullable=True)
    top_k = Column(Integer, nullable=True)
    mcp_tool_id = Column(String(128), nullable=True)
    kind = Column(SmallInteger, nullable=False, default=0)
    prompt_snippet = Column(Text, nullable=True)
    prompt_template = Column(Text, nullable=True)
    param_prompt_template = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    enabled = Column(SmallInteger, nullable=False, default=1)
    create_by = Column(String(20), nullable=True)
    update_by = Column(String(20), nullable=True)
    create_time = Column(DateTime, nullable=False, default=datetime.now)
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    deleted = Column(SmallInteger, nullable=False, default=0)
