from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserItem(BaseModel):
    id: str
    username: str
    role: str
    status: int = 1
    avatar: Optional[str] = None
    createTime: Optional[datetime] = None
    updateTime: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserCreatePayload(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"
    status: Optional[int] = 1
    avatar: Optional[str] = None

class UserUpdatePayload(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    status: Optional[int] = None
    avatar: Optional[str] = None

class ChangePasswordPayload(BaseModel):
    currentPassword: str
    newPassword: str
