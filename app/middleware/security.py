"""
安全中间件套件
══════════════

包含：
1. SecurityHeadersMiddleware — 添加安全响应头
2. InputSanitizer — 用户输入 HTML 标签过滤
3. startup_validation — 启动时检查敏感配置
"""
import re
import html
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ────────────────────────────────
# 1. 安全响应头中间件
# ────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    为所有响应添加安全相关的 HTTP 头，防御常见 Web 攻击。

    - X-Content-Type-Options: 禁止 MIME 嗅探
    - X-Frame-Options: 禁止被嵌入 iframe（防点击劫持）
    - X-XSS-Protection: 启用浏览器 XSS 过滤器（旧版浏览器兜底）
    - Content-Security-Policy: 资源加载白名单
    - Referrer-Policy: 限制 referrer 泄露
    - Strict-Transport-Security: 强制 HTTPS（生产环境启用）
    """
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # 基础 CSP：只允许同源资源 + 内联样式/脚本
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # 生产环境启用 HSTS（注释：需要 HTTPS 才生效）
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# ────────────────────────────────
# 2. 输入清洗工具
# ────────────────────────────────

# 允许出现的 HTML 标签白名单（当前为空——不允许任何 HTML）
ALLOWED_HTML_TAGS: set[str] = set()


def sanitize_html(value: str | None, max_length: int = 0) -> str:
    """
    清洗用户输入的字符串：
    - 剥离所有 HTML 标签（防 XSS）
    - HTML 实体转义
    - 可选截断长度
    """
    if value is None:
        return ""
    # 剥离标签
    clean = re.sub(r"<[^>]*>", "", value)
    # HTML 实体转义
    clean = html.escape(clean, quote=True)
    # 截断
    if max_length > 0 and len(clean) > max_length:
        clean = clean[:max_length]
    return clean


def sanitize_user_input(data: dict, fields: list[str], max_length: int = 0) -> dict:
    """批量清洗字典中的多个字段"""
    for field in fields:
        if field in data and data[field] is not None:
            data[field] = sanitize_html(str(data[field]), max_length)
    return data


# ────────────────────────────────
# 3. 启动时安全校验
# ────────────────────────────────

def startup_validation(config: dict) -> list[str]:
    """
    启动时校验安全配置，返回警告信息列表。
    在 main.py 的 lifespan 中调用。
    """
    warnings: list[str] = []

    secret_key = config.get("SECRET_KEY", "")
    if not secret_key or len(secret_key) < 16:
        warnings.append("⚠️  SECRET_KEY 为空或太短（需要 >= 16 字符），JWT 签名可被伪造！")
    if secret_key in ("your-secret-key-change-it", "changeme"):
        warnings.append("⚠️  SECRET_KEY 使用了默认值，请立即修改！")

    dashscope_key = config.get("DASHSCOPE_API_KEY", "")
    if not dashscope_key or len(dashscope_key) < 10:
        warnings.append("⚠️  DASHSCOPE_API_KEY 未配置，AI 问答功能不可用")

    cors_origins = config.get("CORS_ORIGINS", "")
    if cors_origins == "*":
        warnings.append("⚠️  CORS 允许所有来源（allow_origins=['*']），生产环境请限制为前端域名")

    return warnings
