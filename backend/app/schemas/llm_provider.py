from pydantic import BaseModel
from typing import List, Optional


class LLMProviderCreateRequest(BaseModel):
    name: str
    base_url: str
    api_key: str


class LLMProviderUpdateRequest(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    enabled_models: Optional[List[str]] = None
    is_active: Optional[int] = None


class LLMProviderVO(BaseModel):
    id: str
    name: str
    base_url: str
    enabled_models: List[str]
    is_active: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
