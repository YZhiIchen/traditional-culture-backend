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

# ── JWT 认证 ──
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))  # 默认 1 小时
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 刷新 token 有效期 7 天

# ── 文件上传 ──
UPLOAD_DIR = BASE_DIR / "uploads"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
MAX_TEXT_SIZE = 1024 * 1024           # 1MB（文本上传）
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
# 文件魔数校验（白名单）
# 前 12 字节即可区分 JPEG/PNG/WebP
FILE_MAGIC: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",  # 开头是 RIFF...WEBP
}

# ── 服务 ──
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# ── CORS 安全配置 ──
# 生产环境请设置为前端域名列表，用逗号分隔
# 例如: https://example.com,https://admin.example.com
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "*")
if CORS_ORIGINS_STR == "*":
    CORS_ORIGINS = ["*"]
else:
    CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]

# ── 速率限制 ──
# 格式: "次数/时间窗口"
RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "5/minute")      # 登录：5次/分钟
RATE_LIMIT_REGISTER = os.getenv("RATE_LIMIT_REGISTER", "3/minute") # 注册：3次/分钟
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")  # 全局：60次/分钟

# ── AI 配置 ──
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
NLP_MODEL = "qwen-plus"
VL_MODEL = "qwen-vl-plus"
TOP_K_RECALL = 3
DEFAULT_PATTERNS = ["dragon pattern", "phoenix pattern", "taotie pattern"]
IMAGE_MAX_SIZE = 1024