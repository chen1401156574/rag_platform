import json
from sqlalchemy import Column, String, Text, DateTime, SmallInteger
from datetime import datetime
from models.base import Base


class LLMProvider(Base):
    __tablename__ = "t_llm_provider"

    id = Column(String(20), primary_key=True)
    name = Column(String(128), nullable=False)
    base_url = Column(String(512), nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    enabled_models = Column(Text, nullable=False, default="[]")
    is_active = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def get_enabled_models(self) -> list[str]:
        try:
            models = json.loads(self.enabled_models)
            return models if isinstance(models, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_enabled_models(self, models: list[str]) -> None:
        self.enabled_models = json.dumps(models, ensure_ascii=False)
