"""
朝代/作者动态管理路由
"""
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Dynasty, Author
from ..utils.auth import require_user
from ..models.user import User
from ..utils.response import success

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.get("/dynasties")
def list_dynasties(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_user)],
):
    """获取所有朝代（自动收录）"""
    items = db.execute(select(Dynasty).order_by(Dynasty.id)).scalars().all()
    return success([d.to_dict() for d in items])


@router.get("/authors")
def list_authors(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_user)],
):
    """获取所有作者（自动收录）"""
    items = db.execute(select(Author).order_by(Author.id)).scalars().all()
    return success([a.to_dict() for a in items])
