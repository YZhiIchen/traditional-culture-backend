"""
检索路由：关键词搜索 / 资源详情
"""
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Resource
from ..utils.auth import require_user
from ..utils.response import success, fail

router = APIRouter(prefix="", tags=["检索"])


@router.get("/search")
def search(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
    keyword: str = Query(default=""),
    type: str | None = Query(default=None),
    dynasty: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
):
    """全局资源检索"""
    query = db.query(Resource).filter(Resource.status == "completed")

    if type and type in ("image", "text"):
        query = query.filter(Resource.file_type == type)

    if dynasty:
        query = query.filter(Resource.dynasty == dynasty)

    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            (Resource.title.ilike(kw)) |
            (Resource.dynasty.ilike(kw)) |
            (Resource.author.ilike(kw)) |
            (Resource.tags.ilike(kw)) |
            (Resource.description.ilike(kw))
        )

    total = query.count()
    items = (
        query.order_by(Resource.created_at.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )

    return success({
        "list": [
            {
                "id": str(r.file_id),
                "title": r.title or r.file_name,
                "type": r.file_type,
                "dynasty": r.dynasty or "",
                "summary": r.description or "",
                "tags": r.tags.split(",") if r.tags else [],
                "createTime": r.created_at.isoformat() if r.created_at else "",
            }
            for r in items
        ],
        "total": total,
    })


@router.get("/detail/{file_id}")
def get_detail(
    file_id: str,
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取资源详情（等同于识别结果）"""
    resource = db.query(Resource).filter(Resource.file_id == file_id).first()
    if not resource:
        return fail(404, "资源不存在")
    return success({
        "id": str(resource.file_id),
        "title": resource.title or resource.file_name,
        "type": resource.file_type,
        "dynasty": resource.dynasty or "",
        "summary": resource.description or "",
        "tags": resource.tags.split(",") if resource.tags else [],
        "createTime": resource.created_at.isoformat() if resource.created_at else "",
    })
