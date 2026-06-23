"""
定时异步任务调度服务 — 基于 APScheduler BackgroundScheduler
后台线程执行，不阻塞 FastAPI 主线程。

定时任务：
1. 每日 02:00 — 清算注销超 30 天的用户及其数据（物理删除）
2. 每小时    — processing 状态超 1 小时的资源自动转为 failed
3. 每日 03:00 — SQLite 数据库文件备份（保留近 7 份）
4. 每 5 分钟  — 刷新 Home 页面全局统计缓存（性能优化）
"""
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import BASE_DIR, DATABASE_URL
from ..database import SessionLocal
from ..models import User, Resource, Favorite

# 注销用户数据保留天数
DELETED_RETENTION_DAYS = 30
# 识别超时阈值（秒）
PROCESSING_TIMEOUT_SECONDS = 3600
# 备份保留份数
BACKUP_KEEP = 7

_scheduler: BackgroundScheduler | None = None


def purge_deleted_users() -> int:
    """清算注销超 30 天的用户及其资源、收藏（物理删除）"""
    db = SessionLocal()
    count = 0
    try:
        threshold = datetime.now() - timedelta(days=DELETED_RETENTION_DAYS)
        users = db.query(User).filter(
            User.deleted_at.isnot(None),
            User.deleted_at < threshold,
        ).all()

        for u in users:
            # 删除该用户的头像文件
            if u.avatar:
                try:
                    avatar_fp = Path(str(BASE_DIR / "uploads" / "headportrait")) / Path(u.avatar).name
                    if avatar_fp.exists():
                        avatar_fp.unlink(missing_ok=True)
                except Exception:
                    pass

            # 删除该用户的资源（含物理文件）
            resources = db.query(Resource).filter(Resource.owner_id == u.id).all()
            for r in resources:
                if r.file_url:
                    fp = Path(str(BASE_DIR / "uploads")) / Path(r.file_url).name
                    if fp.exists():
                        fp.unlink(missing_ok=True)
                db.delete(r)

            # 删除该用户的收藏
            db.query(Favorite).filter(Favorite.user_id == u.id).delete()

            db.delete(u)
            count += 1

        db.commit()
        if count:
            print(f"[Scheduler] 清算 {count} 个过期注销用户")
        return count
    except Exception as e:
        db.rollback()
        print(f"[Scheduler] 清算注销用户失败: {e}")
        return 0
    finally:
        db.close()


def expire_processing_resources() -> int:
    """将 processing 超时资源自动转为 failed"""
    db = SessionLocal()
    count = 0
    try:
        threshold = datetime.now() - timedelta(seconds=PROCESSING_TIMEOUT_SECONDS)
        items = db.query(Resource).filter(
            Resource.status == "processing",
            Resource.created_at < threshold,
        ).all()
        for r in items:
            r.status = "failed"
            count += 1
        db.commit()
        if count:
            print(f"[Scheduler] {count} 条超时资源转为 failed")
        return count
    except Exception as e:
        db.rollback()
        print(f"[Scheduler] 超时资源处理失败: {e}")
        return 0
    finally:
        db.close()


def backup_database() -> str | None:
    """备份 SQLite 数据库文件，保留近 7 份"""
    try:
        db_path = DATABASE_URL.replace("sqlite:///", "")
        src = Path(db_path)
        if not src.exists():
            return None

        backup_dir = BASE_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = backup_dir / f"data_{stamp}.db"
        shutil.copy2(src, dst)

        # 清理旧备份，仅保留最近 BACKUP_KEEP 份
        backups = sorted(backup_dir.glob("data_*.db"), key=lambda p: p.stat().st_mtime)
        for old in backups[:-BACKUP_KEEP]:
            old.unlink(missing_ok=True)

        print(f"[Scheduler] 数据库已备份: {dst.name}")
        return str(dst)
    except Exception as e:
        print(f"[Scheduler] 数据库备份失败: {e}")
        return None


def refresh_dashboard_cache() -> None:
    """刷新 Home 页面全局统计缓存（由调度器每 5 分钟调用）"""
    try:
        from ..routers.dashboard import refresh_global_stats_cache
        refresh_global_stats_cache()
    except Exception as e:
        print(f"[Scheduler] 刷新仪表盘缓存失败: {e}")


def start_scheduler() -> BackgroundScheduler:
    """启动后台调度器"""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # 1. 每日 02:00 清算过期注销用户
    _scheduler.add_job(
        purge_deleted_users,
        trigger=CronTrigger(hour=2, minute=0),
        id="purge_deleted_users",
        replace_existing=True,
    )

    # 2. 每小时处理超时识别资源
    _scheduler.add_job(
        expire_processing_resources,
        trigger=IntervalTrigger(hours=1),
        id="expire_processing_resources",
        replace_existing=True,
    )

    # 3. 每日 03:00 备份数据库
    _scheduler.add_job(
        backup_database,
        trigger=CronTrigger(hour=3, minute=0),
        id="backup_database",
        replace_existing=True,
    )

    # 4. 每 5 分钟刷新 Home 页面全局统计缓存
    _scheduler.add_job(
        refresh_dashboard_cache,
        trigger=IntervalTrigger(minutes=5),
        id="refresh_dashboard_cache",
        replace_existing=True,
    )
    # 启动时立即刷新一次，避免首次请求冷启动
    _scheduler.add_job(
        refresh_dashboard_cache,
        id="refresh_dashboard_cache_init",
        replace_existing=True,
    )

    _scheduler.start()
    print("[Scheduler] 后台调度器已启动")
    return _scheduler


def shutdown_scheduler() -> None:
    """关闭后台调度器"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print("[Scheduler] 后台调度器已关闭")