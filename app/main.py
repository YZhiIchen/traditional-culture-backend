"""
FastAPI 应用入口 + 路由注册

安全加固：
- SecurityHeadersMiddleware: 安全响应头（XSS/XFO/CSP）
- CORS: 按配置限定的域名
- 全局速率限制（slowapi）
- 启动时校验 SECRET_KEY / DASHSCOPE_API_KEY
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import (
    UPLOAD_DIR, CORS_ORIGINS,
    RATE_LIMIT_DEFAULT,
    SECRET_KEY, DASHSCOPE_API_KEY,
)
from .database import init_db
from .services.scheduler_service import start_scheduler, shutdown_scheduler
from .middleware.security import SecurityHeadersMiddleware, startup_validation
from .routers.auth import router as auth_router, user_router
from .routers.upload import router as upload_router
from .routers.recognition import router as recognition_router
from .routers.search import router as search_router
from .routers.dashboard import router as dashboard_router
from .routers.explore import router as explore_router
from .routers.favorite import router as favorite_router
from .routers.knowledge import router as knowledge_router
from .routers.chat import router as chat_router

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── 全局速率限制器 ──
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT_DEFAULT])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库 + 后台调度器 + 安全校验"""
    logger.info("=" * 50)
    logger.info("传统文化数字化平台后端启动")
    logger.info("=" * 50)

    # 启动安全校验
    warnings = startup_validation({
        "SECRET_KEY": SECRET_KEY,
        "DASHSCOPE_API_KEY": DASHSCOPE_API_KEY,
        "CORS_ORIGINS": str(CORS_ORIGINS),
    })
    if warnings:
        for w in warnings:
            logger.warning(w)
    else:
        logger.info("✅ 安全配置检查通过")

    init_db()
    start_scheduler()
    logger.info("✅ 数据库初始化完成，调度器已启动")

    yield

    shutdown_scheduler()
    logger.info("🛑 调度器已关闭")


app = FastAPI(
    title="传统文化数字化平台 API",
    description="基于 NLP 和图像识别的传统文化数字化保护与传承研究 — 后端服务",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",        # Swagger 文档
    redoc_url="/api/redoc",      # ReDoc 文档
)

# ── 安全响应头 ──
app.add_middleware(SecurityHeadersMiddleware)

# ── CORS（按配置限定来源） ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Refresh-Token"],
)

# ── 速率限制 ──
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── 静态文件（上传的文件可通过 /uploads/ 访问） ──
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# ── 注册路由 ──
app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(recognition_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(explore_router, prefix="/api")
app.include_router(favorite_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


@app.get("/api/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "service": "traditional-culture-backend"}