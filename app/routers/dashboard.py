"""
仪表盘路由：统计数据 / 标签云 / 朝代分布
"""
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Resource, User
from ..utils.auth import require_user
from ..utils.response import success

router = APIRouter(prefix="/dashboard", tags=["工作台"])


@router.get("/stats")
def get_stats(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取当前用户的统计数据（非全局）"""
    from datetime import datetime, timedelta

    uid = current_user.id
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = datetime.now() - timedelta(days=7)

    base = db.query(Resource).filter(Resource.owner_id == uid)

    total_resources = base.count()
    total_recognized = base.filter(Resource.status == "completed").count()
    week_new = base.filter(Resource.created_at >= week_ago).count()
    today_upload = base.filter(Resource.created_at >= today).count()

    avg_confidence = db.query(func.avg(Resource.confidence)).filter(
        Resource.owner_id == uid,
        Resource.confidence.isnot(None)
    ).scalar()
    avg_pct = round((avg_confidence or 0.9) * 100, 1)

    return success({
        "totalResources": total_resources,
        "totalRecognized": total_recognized,
        "weekNew": week_new,
        "avgConfidence": f"{avg_pct}%",
        "todayUpload": today_upload,
        "todayRecognized": total_recognized,
        "todaySearch": 0,
    })


@router.get("/tags")
def get_hot_tags(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取当前用户的热门标签"""
    resources = db.query(Resource.tags).filter(
        Resource.tags.isnot(None),
        Resource.owner_id == current_user.id
    ).all()

    tag_count: dict[str, int] = {}
    for (tags_str,) in resources:
        for tag in tags_str.split(","):
            tag = tag.strip()
            if tag:
                tag_count[tag] = tag_count.get(tag, 0) + 1

    sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)[:20]
    return success([
        {"name": name, "count": count}
        for name, count in sorted_tags
    ])


@router.get("/dynasties")
def get_dynasties(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取当前用户的朝代分布统计"""
    results = (
        db.query(Resource.dynasty, func.count(Resource.id))
        .filter(
            Resource.dynasty.isnot(None),
            Resource.owner_id == current_user.id
        )
        .group_by(Resource.dynasty)
        .all()
    )

    total = sum(count for _, count in results)
    return success([
        {
            "name": dynasty,
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0,
        }
        for dynasty, count in results
    ])
