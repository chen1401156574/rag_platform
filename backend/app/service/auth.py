import logging
import os
import secrets
from datetime import timedelta

from fastapi import HTTPException, Security, status
from fastapi_jwt import JwtAccessBearerCookie, JwtAuthorizationCredentials
from sqlalchemy.exc import SQLAlchemyError

from exceptions.auth import AuthError
from models.user import User
from utils.database import get_db
from utils.password import verify_password


JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "default_secret_key") + "happy"

access_security = JwtAccessBearerCookie(
    secret_key=JWT_SECRET_KEY,
    auto_error=True,
    access_expires_delta=timedelta(days=2),
)


def _status_to_int(value) -> int:
    if value in (0, "0", False):
        return 0
    return 1


def create_token(user_id: int, user_name: str, salting: str = "", role: str = "user", status: int = 1):
    subject = {
        "user_id": user_id,
        "user_name": user_name,
        "role": role or "user",
        "status": _status_to_int(status),
        "salting": salting or secrets.token_hex(16),
    }
    return access_security.create_access_token(subject=subject)


async def require_admin(credentials: JwtAuthorizationCredentials = Security(access_security)):
    subject = credentials.subject or {}
    if _status_to_int(subject.get("status", 1)) != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    if subject.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can access this resource")
    return credentials


def authenticate(username: str, password: str) -> str:
    db = next(get_db())
    try:
        user = db.query(User).filter(User.username == username, User.deleted == 0).first()
        if not user:
            raise AuthError("认证失败")

        if not verify_password(password, user.password_hash):
            raise AuthError("认证失败")

        if _status_to_int(getattr(user, "status", 1)) != 1:
            raise AuthError("账号已停用")

        return create_token(
            user.id,
            user.username,
            role=getattr(user, "role", "user") or "user",
            status=getattr(user, "status", 1),
        )

    except SQLAlchemyError as e:
        raise AuthError("认证失败") from e
    finally:
        db.close()


def register_user(username: str, password: str):
    from utils.password import hash_password

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    db = next(get_db())
    try:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise AuthError("用户名已存在")

        password_hash = hash_password(password)
        new_user = User(username=username, password_hash=password_hash)
        db.add(new_user)
        db.commit()
        logger.info("User %s registered successfully", username)

    except SQLAlchemyError as e:
        logger.error("Database operation failed: %s", str(e))
        db.rollback()
        raise AuthError(f"注册失败: {str(e)}")
    except Exception as e:
        logger.error("Registration failed: %s", str(e))
        db.rollback()
        raise AuthError(f"注册失败: {str(e)}")
    finally:
        db.close()
