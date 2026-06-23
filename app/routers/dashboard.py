"""
仪表盘路由：全局统计 / 用户统计 / 标签云 / 朝代分布 / 最近活动

性能优化：
- 全局统计使用内存缓存，由调度器每 5 分钟刷新
- 接口直接读缓存，避免每次请求都执行重聚合查询
"""
import time
from datetime import datetime, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Resource, User
from ..utils.auth import require_user
from ..utils.response import success

router = APIRouter(prefix="/dashboard", tags=["工作台"])

# ── 全局统计内存缓存 ──
_cache: dict = {"data": None, "ts": 0}
_CACHE_TTL = 300  # 5 分钟


def _compute_global_stats(db: Session) -> dict:
    """计算全局统计（耗时聚合查询，结果由调度器缓存）"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = datetime.now() - timedelta(days=7)

    total_resources = db.query(Resource).count()
    total_recognized = db.query(Resource).filter(Resource.status == "completed").count()
    week_new = db.query(Resource).filter(Resource.created_at >= week_ago).count()
    today_upload = db.query(Resource).filter(Resource.created_at >= today).count()
    today_recognized = db.query(Resource).filter(
        Resource.status == "completed",
        Resource.recognition_time >= today,
    ).count()

    avg_confidence = db.query(func.avg(Resource.confidence)).filter(
        Resource.confidence.isnot(None)
    ).scalar()
    avg_pct = round((avg_confidence or 0.9) * 100, 1)

    total_users = db.query(User).filter(User.deleted_at.is_(None)).count()

    return {
        "totalResources": total_resources,
        "totalRecognized": total_recognized,
        "weekNew": week_new,
        "avgConfidence": f"{avg_pct}%",
        "todayUpload": today_upload,
        "todayRecognized": today_recognized,
        "totalUsers": total_users,
    }


def refresh_global_stats_cache(db: Session | None = None) -> dict:
    """刷新全局统计缓存（由调度器或首次请求调用）"""
    from ..database import SessionLocal
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        data = _compute_global_stats(db)
        _cache["data"] = data
        _cache["ts"] = time.time()
        print("[Dashboard] 全局统计缓存已刷新")
        return data
    except Exception as e:
        print(f"[Dashboard] 刷新缓存失败: {e}")
        return _cache.get("data") or {}
    finally:
        if own_session:
            db.close()


def _get_cached_stats(db: Session) -> dict:
    """获取缓存的全局统计，过期则重新计算"""
    if _cache["data"] is None or (time.time() - _cache["ts"]) > _CACHE_TTL:
        refresh_global_stats_cache(db)
    return _cache["data"] or {}


# ── 全局统计接口 ──

@router.get("/global-stats")
def get_global_stats(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取系统全局统计（读缓存，性能友好）"""
    return success(_get_cached_stats(db))


@router.get("/global-tags")
def get_global_hot_tags(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取全局热门标签 Top 20"""
    resources = db.query(Resource.tags).filter(
        Resource.tags.isnot(None),
        Resource.status == "completed",
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


@router.get("/global-dynasties")
def get_global_dynasties(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取全局朝代分布统计"""
    results = (
        db.query(Resource.dynasty, func.count(Resource.id))
        .filter(
            Resource.dynasty.isnot(None),
            Resource.dynasty != "",
            Resource.status == "completed",
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


@router.get("/recent-activity")
def get_recent_activity(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取全局最近识别活动（前 8 条，含上传者信息）"""
    items = (
        db.query(Resource, User.nickname)
        .join(User, Resource.owner_id == User.id)
        .filter(Resource.status == "completed")
        .order_by(Resource.recognition_time.desc())
        .limit(8)
        .all()
    )

    return success([
        {
            "id": str(r.file_id),
            "title": r.title or r.file_name,
            "dynasty": r.dynasty or "",
            "type": r.file_type,
            "time": r.recognition_time.isoformat() if r.recognition_time else "",
            "status": "done",
            "uploader": nickname,
        }
        for r, nickname in items
    ])


# ── 用户个人统计接口（保留原有） ──

@router.get("/stats")
def get_stats(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取当前用户的个人统计数据"""
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
