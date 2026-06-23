"""
知识发现路由：推荐内容 / 知识图谱
"""
from typing import Annotated
import random
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Resource, User
from ..utils.auth import require_user
from ..utils.response import success

router = APIRouter(prefix="/explore", tags=["知识发现"])


@router.get("/recommend")
def get_recommend(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
    dynasty: str | None = Query(default=None),
    category: str | None = Query(default=None),
):
    """获取全局精选推荐（展示全系统高质量识别结果）"""
    query = db.query(Resource).filter(
        Resource.status == "completed",
        Resource.confidence.isnot(None),
    )

    if dynasty:
        query = query.filter(Resource.dynasty == dynasty)

    items = query.order_by(Resource.confidence.desc()).limit(12).all()

    return success([
        {
            "id": str(r.file_id),
            "title": r.title or r.file_name,
            "desc": r.description or "",
            "dynasty": r.dynasty or "未知",
            "author": r.author or "佚名",
            "category": (r.tags.split(",")[0] if r.tags else r.file_type),
            "tags": r.tags.split(",") if r.tags else [],
            "confidence": r.confidence or 0.8,
        }
        for r in items
        if r.confidence
    ][:6])


@router.get("/graph")
def get_graph(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取知识图谱关联边"""
    authors = (
        db.query(Resource.author, Resource.tags)
        .filter(Resource.author.isnot(None), Resource.author != "佚名", Resource.tags.isnot(None))
        .distinct(Resource.author)
        .limit(10)
        .all()
    )

    relations = ["开创", "影响", "传承", "融合", "交汇"]
    edges = []

    for author, tags_str in authors:
        if tags_str:
            tags = tags_str.split(",")
            if tags:
                tag = random.choice(tags).strip()
                edges.append({
                    "from": author,
                    "relation": random.choice(relations),
                    "to": tag if tag else "传统文化",
                })

    # 如果太少，补充一些关联
    default_edges = [
        {"from": "王维", "relation": "开创", "to": "文人山水画"},
        {"from": "苏轼", "relation": "影响", "to": "宋代书法"},
        {"from": "敦煌", "relation": "交汇", "to": "丝绸之路"},
        {"from": "青花", "relation": "融合", "to": "伊斯兰纹样"},
        {"from": "颜真卿", "relation": "传承", "to": "唐代楷书"},
        {"from": "诗经", "relation": "影响", "to": "后世诗词"},
        {"from": "佛教", "relation": "催生", "to": "石窟艺术"},
    ]

    result = edges[:5] + default_edges[len(edges):]
    return success(result[:7])
