"""
启动入口
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    print(f"=== 传统文化数字化平台后端 ===")
    print(f"启动 => http://{HOST}:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
