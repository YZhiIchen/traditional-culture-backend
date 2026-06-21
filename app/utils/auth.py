"""
JWT 鉴权工具

功能：
- 短期 access_token（默认 1 小时）
- 长期 refresh_token（7 天）
- 过期自动刷新
- 强制鉴权 / 可选鉴权
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated

from jose import jwt, ExpiredSignatureError, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..config import (
    SECRET_KEY, ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from ..database import get_db
from ..models import User

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: int) -> str:
    """生成短期 JWT Access Token（默认 1 小时）"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """生成长期 Refresh Token（7 天）"""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """解码 Token，返回完整 payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        return None
    except JWTError:
        return None


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[Session, Depends(get_db)]
) -> User | None:
    """获取当前登录用户（可选鉴权）"""
    if not credentials:
        return None
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        return None
    user_id = int(payload.get("sub", 0))
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_user(current_user: Annotated[User | None, Depends(get_current_user)]) -> User:
    """强制鉴权：未登录抛出 401"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return current_user


def refresh_access_token(refresh_token: str) -> str | None:
    """
    用 refresh_token 换取新的 access_token。
    - 成功：返回新 access_token
    - 失败（过期/无效）：返回 None
    """
    payload = decode_token(refresh_token)
    if payload is None:
        return None
    if payload.get("type") != "refresh":
        return None
    user_id = int(payload.get("sub", 0))
    if not user_id:
        return None
    return create_access_token(user_id)
