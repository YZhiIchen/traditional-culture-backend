"""
启动入口
    python run.py
    或
    uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
"""
import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    print(f"[传统] 传统文化数字化平台后端启动 => http://{HOST}:{PORT}")
    print(f"[API] API 文档 => http://{HOST}:{PORT}/docs")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
