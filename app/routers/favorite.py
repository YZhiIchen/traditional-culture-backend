"""
收藏路由（使用 file_id 字符串）
"""
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Resource, Favorite
from ..utils.auth import require_user
from ..utils.response import success, fail

router = APIRouter(prefix="/favorite", tags=["收藏"])


def _resolve_resource_id(db: Session, file_id: str) -> int | None:
    """将 file_id (字符串) 转为 Resource.id (整数)"""
    r = db.query(Resource.id).filter(Resource.file_id == file_id).first()
    return r[0] if r else None


@router.post("/{file_id}")
def add_favorite(
    file_id: str,
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    rid = _resolve_resource_id(db, file_id)
    if rid is None:
        return fail(404, "资源不存在")
    existing = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.resource_id == rid,
    ).first()
    if existing:
        return fail(400, "已经收藏过了")
    db.add(Favorite(user_id=current_user.id, resource_id=rid))
    db.commit()
    return success(None, "收藏成功")


@router.delete("/{file_id}")
def remove_favorite(
    file_id: str,
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    rid = _resolve_resource_id(db, file_id)
    if rid is None:
        return success(None, "已取消收藏")
    db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.resource_id == rid,
    ).delete()
    db.commit()
    return success(None, "已取消收藏")


@router.get("/list")
def get_favorites(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    favs = db.query(Favorite).filter(Favorite.user_id == current_user.id).all()
    rids = [f.resource_id for f in favs]
    if not rids:
        return success([])
    resources = db.query(Resource).filter(Resource.id.in_(rids)).all()
    return success([r.to_dict() for r in resources])


@router.get("/check/{file_id}")
def check_favorite(
    file_id: str,
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    rid = _resolve_resource_id(db, file_id)
    if rid is None:
        return success({"favorited": False})
    existing = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.resource_id == rid,
    ).first()
    return success({"favorited": existing is not None})
