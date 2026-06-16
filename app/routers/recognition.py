"""
识别结果路由：详情 / 历史 / 删除
"""
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pathlib import Path
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import User, Resource
from ..utils.auth import require_user
from ..utils.response import success, fail

router = APIRouter(prefix="/recognition", tags=["识别结果"])


@router.get("/result/{file_id}")
def get_result(
    file_id: str,
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取单个识别结果详情"""
    resource = db.query(Resource).filter(Resource.file_id == file_id).first()
    if not resource:
        return fail(404, "资源不存在")
    return success(resource.to_dict())


@router.get("/history")
def get_history(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize"),
    keyword: str | None = Query(default=None),
    type: str | None = Query(default=None),
):
    """获取当前用户的识别历史（分页）"""
    query = db.query(Resource).filter(Resource.owner_id == current_user.id)

    if type and type in ("image", "text"):
        query = query.filter(Resource.file_type == type)

    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            (Resource.title.ilike(kw)) |
            (Resource.dynasty.ilike(kw)) |
            (Resource.author.ilike(kw)) |
            (Resource.tags.ilike(kw))
        )

    total = query.count()
    items = (
        query.order_by(Resource.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return success({
        "list": [r.to_dict() for r in items],
        "total": total,
    })


@router.delete("/{file_id}")
def delete_result(
    file_id: str,
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """删除识别记录"""
    resource = db.query(Resource).filter(
        Resource.file_id == file_id,
        Resource.owner_id == current_user.id,
    ).first()
    if not resource:
        return fail(404, "资源不存在")

    # 删除物理文件（如果是图片且文件存在）
    if resource.file_url:
        file_path = Path(str(UPLOAD_DIR)) / Path(resource.file_url).name
        if file_path.exists():
            file_path.unlink(missing_ok=True)

    db.delete(resource)
    db.commit()
    return success(None, "已删除")
