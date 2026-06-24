"""
知识发现路由：推荐内容 / 知识图谱 / 分类统计 / 朝代统计
"""
import random
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from ..database import get_db
from ..models import Resource, User
from ..utils.auth import require_user
from ..utils.response import success

router = APIRouter(prefix="/explore", tags=["知识发现"])

# 分类关键词映射：前端分类 key → 数据库 tags 中可能包含的关键词
CATEGORY_KEYWORDS = {
    "calligraphy": ["书法", "碑帖", "行书", "楷书", "草书", "隶书", "篆书"],
    "painting": ["绘画", "山水", "花鸟", "水墨", "卷轴", "画卷"],
    "poetry": ["诗词", "文献", "诗经", "唐诗", "宋词", "诗歌", "古籍"],
    "artifact": ["器物", "青花", "瓷器", "青铜", "玉器", "工艺"],
    "sculpture": ["石窟", "造像", "雕塑", "佛像", "彩塑"],
    "architecture": ["古建", "园林", "建筑", "寺庙", "宫殿"],
}

# 标准朝代列表 + 别名映射（数据库中可能是"宋代"、"北宋"等，统一归入"宋"）
DYNASTY_ALIASES = {
    "先秦": ["先秦", "夏", "商", "周", "春秋", "战国"],
    "汉": ["汉", "汉代", "西汉", "东汉", "汉朝"],
    "魏晋": ["魏晋", "三国", "晋", "西晋", "东晋", "南北朝", "魏", "北魏"],
    "唐": ["唐", "唐代", "唐朝", "初唐", "盛唐", "中唐", "晚唐"],
    "宋": ["宋", "宋代", "宋朝", "北宋", "南宋", "北宋代", "南宋代"],
    "元": ["元", "元代", "元朝"],
    "明": ["明", "明代", "明朝"],
    "清": ["清", "清代", "清朝"],
}

DYNASTY_COLORS = {
    "先秦": "oklch(60% 0.08 55)",
    "汉": "oklch(58% 0.09 45)",
    "魏晋": "oklch(56% 0.1 35)",
    "唐": "var(--cinnabar)",
    "宋": "oklch(65% 0.12 75)",
    "元": "oklch(60% 0.08 145)",
    "明": "oklch(52% 0.07 250)",
    "清": "oklch(55% 0.05 300)",
}


def _match_dynasty(raw: str) -> str | None:
    """将数据库中的朝代名归一化到标准朝代名"""
    if not raw:
        return None
    for standard, aliases in DYNASTY_ALIASES.items():
        for alias in aliases:
            if alias in raw:
                return standard
    return None


@router.get("/recommend")
def get_recommend(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
    dynasty: str | None = Query(default=None),
    category: str | None = Query(default=None),
):
    """获取全局精选推荐（展示全系统高质量识别结果）

    支持按朝代和分类筛选：
    - dynasty: 标准朝代名（如 "唐"、"宋"），后端用模糊匹配
    - category: 分类 key（如 "calligraphy"、"painting"）
    """
    query = db.query(Resource).filter(
        Resource.status == "completed",
        Resource.confidence.isnot(None),
    )

    if dynasty:
        # 模糊匹配：将标准朝代名展开为所有别名，用 OR + LIKE 匹配
        aliases = DYNASTY_ALIASES.get(dynasty, [dynasty])
        conditions = [Resource.dynasty.like(f"%{a}%") for a in aliases]
        query = query.filter(or_(*conditions))

    if category and category in CATEGORY_KEYWORDS:
        keywords = CATEGORY_KEYWORDS[category]
        conditions = [Resource.tags.like(f"%{kw}%") for kw in keywords]
        query = query.filter(or_(*conditions))

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


@router.get("/categories")
def get_categories(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
    dynasty: str | None = Query(default=None),
):
    """获取分类统计（基于全局资源的 tags 分布）

    支持按朝代筛选：传入 dynasty 参数时，只统计该朝代下的分类数量。
    """
    query = db.query(Resource.tags).filter(
        Resource.tags.isnot(None),
        Resource.status == "completed",
    )

    # 按朝代模糊筛选
    if dynasty:
        aliases = DYNASTY_ALIASES.get(dynasty, [dynasty])
        conditions = [Resource.dynasty.like(f"%{a}%") for a in aliases]
        query = query.filter(or_(*conditions))

    resources = query.all()

    category_counts = {key: 0 for key in CATEGORY_KEYWORDS}
    for (tags_str,) in resources:
        for cat_key, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in tags_str:
                    category_counts[cat_key] += 1
                    break

    label_map = {
        "calligraphy": "书法碑帖",
        "painting": "绘画卷轴",
        "poetry": "诗词文献",
        "artifact": "器物工艺",
        "sculpture": "石窟造像",
        "architecture": "古建园林",
    }

    return success([
        {"key": key, "label": label_map[key], "count": count}
        for key, count in category_counts.items()
    ])


@router.get("/dynasty-counts")
def get_dynasty_counts(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取朝代分布及数量（用于时间轴展示）

    将数据库中各种朝代写法（"宋代"、"北宋"、"唐朝"等）归一化到标准朝代名。
    """
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

    # 归一化：将数据库中的朝代名映射到标准朝代，合并计数
    standard_counts: dict[str, int] = {d: 0 for d in DYNASTY_ALIASES}
    for raw_dynasty, count in results:
        standard = _match_dynasty(raw_dynasty)
        if standard:
            standard_counts[standard] += count
        # 未匹配到标准朝代的不显示

    return success([
        {
            "name": dynasty,
            "count": count,
            "color": DYNASTY_COLORS.get(dynasty, "var(--cinnabar)"),
        }
        for dynasty, count in standard_counts.items()
    ])


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
