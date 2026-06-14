from pydantic import BaseModel
from typing import List, Optional

class IntentNodeCreateRequest(BaseModel):
    kbId: Optional[str] = None
    intentCode: str
    name: str
    level: int
    parentCode: Optional[str] = None
    description: Optional[str] = None
    examples: Optional[List[str]] = None
    collectionName: Optional[str] = None
    mcpToolId: Optional[str] = None
    topK: Optional[int] = None
    kind: Optional[int] = 0
    sortOrder: Optional[int] = 0
    enabled: Optional[int] = 1
    promptSnippet: Optional[str] = None
    promptTemplate: Optional[str] = None
    paramPromptTemplate: Optional[str] = None

class IntentNodeUpdateRequest(BaseModel):
    name: Optional[str] = None
    level: Optional[int] = None
    parentCode: Optional[str] = None
    description: Optional[str] = None
    examples: Optional[List[str]] = None
    collectionName: Optional[str] = None
    mcpToolId: Optional[str] = None
    topK: Optional[int] = None
    kind: Optional[int] = None
    sortOrder: Optional[int] = None
    enabled: Optional[int] = None
    promptSnippet: Optional[str] = None
    promptTemplate: Optional[str] = None
    paramPromptTemplate: Optional[str] = None

class IntentNodeBatchRequest(BaseModel):
    ids: List[str]

class IntentNodeTreeVO(BaseModel):
    id: str
    intentCode: str
    name: str
    level: int
    parentCode: Optional[str] = None
    description: Optional[str] = None
    examples: Optional[str] = None
    collectionName: Optional[str] = None
    topK: Optional[int] = None
    kind: int
    sortOrder: int
    enabled: int
    mcpToolId: Optional[str] = None
    promptSnippet: Optional[str] = None
    promptTemplate: Optional[str] = None
    paramPromptTemplate: Optional[str] = None
    children: List['IntentNodeTreeVO'] = []

    class Config:
        from_attributes = True

# 解决循环引用声明
IntentNodeTreeVO.model_rebuild()
