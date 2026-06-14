from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from models.user import User
from schemas.user_admin import ChangePasswordPayload, UserCreatePayload, UserUpdatePayload
from service.auth import access_security
from utils.database import get_db
from utils.password import hash_password, verify_password
from utils.response import error_result, success_result

router = APIRouter()


def _normalize_status(value: Optional[int]) -> int:
    return 0 if value in (0, "0", False) else 1


def _parse_user_id(user_id: str) -> Optional[int]:
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def _avatar_for(username: str) -> str:
    return f"https://api.dicebear.com/7.x/adventurer/svg?seed={username}"


def _format_dt(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _user_record(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "role": user.role or "user",
        "status": _normalize_status(user.status),
        "avatar": _avatar_for(user.username),
        "createTime": _format_dt(getattr(user, "created_at", None)),
        "updateTime": _format_dt(getattr(user, "updated_at", None)),
    }


@router.get("/users")
@router.get("/user/page")
async def get_users_page(
    current: int = 1,
    size: int = 10,
    keyword: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        page = max(current, 1)
        page_size = max(size, 1)
        filters = [User.deleted == 0]
        if keyword:
            like = f"%{keyword}%"
            filters.append(or_(User.username.like(like), User.role.like(like)))
        if status is not None:
            filters.append(User.status == _normalize_status(status))

        total = db.scalar(select(func.count()).select_from(User).where(and_(*filters))) or 0
        users = db.scalars(
            select(User)
            .where(and_(*filters))
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        return success_result(
            data={
                "records": [_user_record(user) for user in users],
                "total": total,
                "size": page_size,
                "current": page,
                "pages": (total + page_size - 1) // page_size,
            }
        )
    except Exception as exc:
        return error_result(code="500", message=str(exc))


@router.post("/users")
@router.post("/user")
async def create_user(
    payload: UserCreatePayload,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        username = payload.username.strip()
        if not username:
            return error_result(code="400", message="用户名不能为空")
        if not payload.password:
            return error_result(code="400", message="密码不能为空")

        existing = db.scalars(select(User).where(User.username == username, User.deleted == 0)).first()
        if existing:
            return error_result(code="400", message=f"用户名已存在: {username}")

        user = User(
            username=username,
            password_hash=hash_password(payload.password),
            role=payload.role or "user",
            status=_normalize_status(payload.status),
            deleted=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return success_result(data=str(user.id))
    except Exception as exc:
        db.rollback()
        return error_result(code="500", message=str(exc))


@router.put("/users/{id}")
@router.put("/user/{id}")
async def update_user(
    id: str,
    payload: UserUpdatePayload,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        user_pk = _parse_user_id(id)
        if user_pk is None:
            return error_result(code="400", message=f"无效用户 ID: {id}")

        user = db.scalars(select(User).where(User.id == user_pk, User.deleted == 0)).first()
        if not user:
            return error_result(code="404", message=f"用户不存在或已删除: id={id}")

        if payload.username is not None:
            username = payload.username.strip()
            if not username:
                return error_result(code="400", message="用户名不能为空")
            conflict = db.scalars(
                select(User).where(User.username == username, User.id != user.id, User.deleted == 0)
            ).first()
            if conflict:
                return error_result(code="400", message=f"用户名已存在: {username}")
            user.username = username

        if payload.password:
            user.password_hash = hash_password(payload.password)
        if payload.role is not None:
            user.role = payload.role or "user"
        if payload.status is not None:
            user.status = _normalize_status(payload.status)

        user.updated_at = datetime.now()
        db.commit()
        return success_result(data=None)
    except Exception as exc:
        db.rollback()
        return error_result(code="500", message=str(exc))


@router.delete("/users/{id}")
@router.delete("/user/{id}")
async def delete_user(
    id: str,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        user_pk = _parse_user_id(id)
        if user_pk is None:
            return error_result(code="400", message=f"无效用户 ID: {id}")

        user = db.scalars(select(User).where(User.id == user_pk, User.deleted == 0)).first()
        if not user:
            return error_result(code="404", message=f"用户不存在或已删除: id={id}")

        if user.username == "admin":
            return error_result(code="400", message="系统管理员账号不能删除")

        user.deleted = 1
        user.status = 0
        user.updated_at = datetime.now()
        db.commit()
        return success_result(data=None)
    except Exception as exc:
        db.rollback()
        return error_result(code="500", message=str(exc))


@router.put("/user/password")
async def change_user_password(
    payload: ChangePasswordPayload,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        user_pk = _parse_user_id(str(credentials.subject.get("user_id")))
        if user_pk is None:
            return error_result(code="401", message="当前登录用户不存在或已停用")

        user = db.scalars(select(User).where(User.id == user_pk, User.deleted == 0)).first()
        if not user or _normalize_status(user.status) != 1:
            return error_result(code="404", message="当前登录用户不存在或已停用")

        if not verify_password(payload.currentPassword, user.password_hash):
            return error_result(code="400", message="当前密码输入错误")

        user.password_hash = hash_password(payload.newPassword)
        user.updated_at = datetime.now()
        db.commit()
        return success_result(data=None)
    except Exception as exc:
        db.rollback()
        return error_result(code="500", message=str(exc))
