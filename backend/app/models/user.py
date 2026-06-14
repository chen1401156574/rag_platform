from sqlalchemy import Column, DateTime, Integer, SmallInteger, String
from sqlalchemy.sql import func
from models.base import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(100), nullable=False)
    role = Column(String(32), nullable=False, default="user")
    status = Column(SmallInteger, nullable=False, default=1)
    deleted = Column(SmallInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
