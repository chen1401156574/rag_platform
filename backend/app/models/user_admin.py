from sqlalchemy import Column, String, SmallInteger, DateTime
from datetime import datetime
from models.base import Base

class UserAdmin(Base):
    __tablename__ = 't_user'

    id = Column(String(20), primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="user")
    avatar = Column(String(128), nullable=True)
    create_time = Column(DateTime, nullable=False, default=datetime.now)
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    deleted = Column(SmallInteger, nullable=False, default=0)
