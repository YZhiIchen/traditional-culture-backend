"""
传统文化数字化平台 — 后端配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载项目根目录 .env 文件
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# 数据库
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data.db'}")

# JWT
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

# 文件上传
UPLOAD_DIR = BASE_DIR / "uploads"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

# 服务
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# AI 配置
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
NLP_MODEL = "qwen-plus"
VL_MODEL = "qwen-vl-plus"
TOP_K_RECALL = 3
DEFAULT_PATTERNS = ["dragon pattern", "phoenix pattern", "taotie pattern"]
IMAGE_MAX_SIZE = 1024