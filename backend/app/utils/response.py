from typing import Any, Optional
from fastapi.responses import JSONResponse

def success_result(data: Any = None, message: str = "success") -> dict:
    """
    返回符合 React 前端要求的成功响应结构
    前端解析时判断 payload.code !== "0" 时为失败，因此成功时 code 需返回字符串 "0"
    """
    return {
        "code": "0",
        "message": message,
        "data": data
    }

def error_result(code: str, message: str, data: Any = None) -> dict:
    """
    返回失败响应结构
    """
    return {
        "code": code,
        "message": message,
        "data": data
    }
