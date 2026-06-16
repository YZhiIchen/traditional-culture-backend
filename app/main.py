"""
FastAPI 应用入口 + 路由注册
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import UPLOAD_DIR
from .database import init_db
from .routers.auth import router as auth_router, user_router
from .routers.upload import router as upload_router
from .routers.recognition import router as recognition_router
from .routers.search import router as search_router
from .routers.dashboard import router as dashboard_router
from .routers.explore import router as explore_router
from .routers.favorite import router as favorite_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    init_db()
    yield


app = FastAPI(
    title="传统文化数字化平台 API",
    description="基于 NLP 和图像识别的传统文化数字化保护与传承研究 — 后端服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS（允许前端开发跨域）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件（上传的文件可通过 /uploads/ 访问）
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# 注册路由
app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(recognition_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(explore_router, prefix="/api")
app.include_router(favorite_router, prefix="/api")


@app.get("/api/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "service": "traditional-culture-backend"}
