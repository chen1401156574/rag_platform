from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordRequestForm
from exceptions.auth import AuthError
from service.auth import authenticate, register_user, access_security
from pydantic import BaseModel
from fastapi_jwt import JwtAuthorizationCredentials
from utils.response import success_result, error_result
import httpx
import asyncio

router = APIRouter()


# 定义登录请求体的 Pydantic 模型
class LoginRequest(BaseModel):
    username: str
    password: str

# 用户认证接口 (兼容原有 API)
@router.post("/login")
async def login(request: LoginRequest):
    try:
        # 调用 authenticate 函数进行认证
        token = authenticate(request.username, request.password)
        return {"access_token": token, "token_type": "bearer"}
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# 前端 Ragent 控制台登录接口
@router.post("/auth/login")
async def auth_login(request: LoginRequest):
    try:
        from utils.database import SessionLocal
        from models.user import User
        from service.auth import create_token
        from utils.password import verify_password

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == request.username, User.deleted == 0).first()
            if not user:
                return error_result(code="401", message="用户不存在")

            if not verify_password(request.password, user.password_hash):
                return error_result(code="401", message="密码错误")

            if getattr(user, "status", 1) != 1:
                return error_result(code="403", message="账号已停用")

            role = getattr(user, "role", "user") or "user"
            user_status = getattr(user, "status", 1)
            token = create_token(user.id, user.username, role=role, status=user_status)
            return success_result(data={
                "userId": str(user.id),
                "username": user.username,
                "role": role,
                "status": user_status,
                "token": f"Bearer {token}",
                "avatar": f"https://api.dicebear.com/7.x/adventurer/svg?seed={user.username}"
            })
        finally:
            db.close()
    except Exception as e:
        return error_result(code="500", message=str(e))

# 前端 Ragent 控制台退出登录
@router.post("/auth/logout")
async def auth_logout():
    return success_result(data=None)

# 前端 Ragent 获取当前登录用户画像
@router.get("/user/me")
async def get_current_user(
    credentials: JwtAuthorizationCredentials = Security(access_security)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        username = str(credentials.subject.get("user_name", "admin"))

        from utils.database import SessionLocal
        from models.user import User

        db = SessionLocal()
        try:
            try:
                user_pk = int(user_id)
            except (TypeError, ValueError):
                user_pk = None
            user = db.query(User).filter(User.id == user_pk, User.deleted == 0).first() if user_pk is not None else None
            if not user:
                user = db.query(User).filter(User.username == username, User.deleted == 0).first()
            if not user:
                return error_result(code="401", message="用户不存在")
            if getattr(user, "status", 1) != 1:
                return error_result(code="403", message="账号已停用")

            return success_result(data={
                "userId": str(user.id),
                "username": user.username,
                "role": getattr(user, "role", "user") or "user",
                "status": getattr(user, "status", 1),
                "avatar": f"https://api.dicebear.com/7.x/adventurer/svg?seed={user.username}"
            })
        finally:
            db.close()
    except Exception as e:
        return error_result(code="401", message="未登录或登录已过期")

# 定义请求体的 Pydantic 模型
class RegisterRequest(BaseModel):
    username: str
    password: str

# 用户注册接口
@router.post("/register")
async def register(request: RegisterRequest):
    try:
        # 调用 register_user 函数进行注册
        register_user(request.username, request.password)
        return {"message": "User registered successfully"}
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# 定义 STS Token 请求体的 Pydantic 模型
class STSTokenRequest(BaseModel):
    appid: str
    accessKey: str

# STS Token 接口
@router.post("/sts-token")
async def get_sts_token(request: STSTokenRequest):
    try:
        # 构造请求头
        headers = {
            "Authorization": f"Bearer; {request.accessKey}",
            "Content-Type": "application/json"
        }

        # 构造请求体
        body = {
            "appid": request.appid,
            "duration": 300
        }

        # 调用 ByteDance STS Token API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openspeech.bytedance.com/api/v1/sts/token",
                headers=headers,
                json=body,
                timeout=30.0
            )

            # 返回原始响应
            return response.json()

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Request timeout when calling STS token API"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error calling STS token API: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
