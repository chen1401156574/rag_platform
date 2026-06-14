from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from models.base import Base


class SystemConfig(Base):
    __tablename__ = 't_system_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(128), unique=True, nullable=False, index=True)
    config_value = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
