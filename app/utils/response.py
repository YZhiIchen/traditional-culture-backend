"""
统一响应格式 — 匹配前端 request.ts 期望：
{ code: 200, message: "ok", data: {...} }
"""
from typing import Any
from fastapi.responses import JSONResponse


def success(data: Any = None, message: str = "ok") -> JSONResponse:
    """成功响应"""
    return JSONResponse(status_code=200, content={
        "code": 200,
        "message": message,
        "data": data
    })


def fail(code: int = 400, message: str = "请求失败", data: Any = None) -> JSONResponse:
    """失败响应"""
    return JSONResponse(status_code=code, content={
        "code": code,
        "message": message,
        "data": data
    })
