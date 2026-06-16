"""
JWT 鉴权工具
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated

from jose import jwt, ExpiredSignatureError, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from ..database import get_db
from ..models import User

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: int) -> str:
    """生成 JWT Token"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> int | None:
    """解码 Token，返回 user_id"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub", 0))
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
    user_id = decode_token(token)
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_user(current_user: Annotated[User | None, Depends(get_current_user)]) -> User:
    """强制鉴权：未登录抛出 401"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return current_user
