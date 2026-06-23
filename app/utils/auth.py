"""
JWT 鉴权工具

功能：
- 短期 access_token（默认 1 小时）
- 长期 refresh_token（7 天）
- 过期自动刷新
- 强制鉴权 / 可选鉴权
- 单点登录：token 携带 token_version，校验版本一致性
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


def create_access_token(user_id: int, token_version: int = 0) -> str:
    """生成短期 JWT Access Token（默认 1 小时）
    token_version 用于单点登录校验，每次登录/登出递增后旧 token 失效。
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
        "ver": token_version,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int, token_version: int = 0) -> str:
    """生成长期 Refresh Token（7 天）
    同样携带 token_version，与 access_token 生命周期一致。
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
        "ver": token_version,
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
    """获取当前登录用户（可选鉴权）

    单点登录校验：token 中的 ver 必须与用户当前 token_version 一致，
    否则说明该账号已在其他设备登录，抛出 401 异常提示被踢下线。
    """
    if not credentials:
        return None
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        return None
    user_id = int(payload.get("sub", 0))
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    # ── 单点登录核心校验 ──
    # token 中的版本号与数据库中不一致 → 账号已在其他设备登录
    token_ver = payload.get("ver", -1)
    if token_ver != user.token_version:
        raise HTTPException(
            status_code=401,
            detail="您的账号已在其他设备登录，请重新登录",
            headers={"X-Kick-Out": "true"},
        )

    return user


def require_user(current_user: Annotated[User | None, Depends(get_current_user)]) -> User:
    """强制鉴权：未登录抛出 401"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return current_user


def refresh_access_token(refresh_token: str, db: Session) -> str | None:
    """
    用 refresh_token 换取新的 access_token。
    - 成功：返回新 access_token
    - 失败（过期/无效/版本不匹配）：返回 None

    单点登录：refresh_token 同样校验 token_version，
    若账号已在其他设备登录则刷新失败，强制重新登录。
    """
    payload = decode_token(refresh_token)
    if payload is None:
        return None
    if payload.get("type") != "refresh":
        return None
    user_id = int(payload.get("sub", 0))
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    # 校验 token_version 一致性
    token_ver = payload.get("ver", -1)
    if token_ver != user.token_version:
        return None

    return create_access_token(user_id, user.token_version)
