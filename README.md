# 传统文化数字化平台 — 后端

> 基于 NLP 与图像识别的传统文化数字化保护与传承研究项目的后端服务。

基于 **Python + FastAPI** 构建，集成 SQLAlchemy ORM、JWT 鉴权、APScheduler 定时任务，调用阿里通义千问（DashScope）大模型完成文物图像识别、文本分析与智能问答。

## 技术栈

| 分类 | 技术 |
| --- | --- |
| Web 框架 | FastAPI 0.115 |
| ASGI 服务器 | Uvicorn |
| ORM | SQLAlchemy 2.0 |
| 数据库 | SQLite（默认，可切换） |
| 鉴权 | JWT（python-jose）+ bcrypt |
| 数据校验 | Pydantic 2 |
| 定时任务 | APScheduler |
| AI 能力 | 阿里通义千问（DashScope）NLP / VL |
| HTTP 客户端 | requests |

## 功能模块（API 路由）

所有接口统一前缀 `/api`：

| 模块 | 路由文件 | 说明 |
| --- | --- | --- |
| 认证 | `routers/auth.py` | 注册、登录、资料、密码、注销 |
| 上传 | `routers/upload.py` | 文件上传 |
| 识别 | `routers/recognition.py` | 图像 / 文本 AI 识别 |
| 搜索 | `routers/search.py` | 资源检索 |
| 探索 | `routers/explore.py` | 资源浏览 |
| 收藏 | `routers/favorite.py` | 收藏管理 |
| 知识库 | `routers/knowledge.py` | 朝代 / 作者知识 |
| AI 问答 | `routers/chat.py` | 智能问答助手 |
| 仪表盘 | `routers/dashboard.py` | 管理后台数据 |

健康检查：`GET /api/health`

## 目录结构

```text
app/
├── middleware/  # 安全中间件（安全响应头 / 输入清洗 / 启动校验）
├── models/      # ORM 模型（user / resource / favorite / dynasty / author）
├── routers/     # 路由层（接口入口）
├── schemas/     # Pydantic 入参 / 出参模型
├── services/    # 业务逻辑（auth / recognition / review / scheduler）
├── utils/       # 工具（auth 鉴权 / response 统一响应）
├── config.py    # 配置加载
├── database.py  # 数据库引擎 + Session
└── main.py      # FastAPI 应用入口
```

## 环境变量

复制 `.env.example` 为 `.env` 并填入真实值：

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `SECRET_KEY` | JWT 签名密钥（生产环境务必修改，至少 16 字符） | — |
| `DATABASE_URL` | 数据库连接字符串 | `sqlite:///./data.db` |
| `HOST` | 服务监听地址 | `0.0.0.0` |
| `PORT` | 服务监听端口 | `8080` |
| `DASHSCOPE_API_KEY` | 阿里通义千问 API 密钥 | — |
| `CORS_ORIGINS` | 允许的跨域来源（逗号分隔，生产环境必填） | `*` |

## 快速开始

### 1. 安装依赖

```sh
pip install -r requirements.txt
```

### 2. 配置环境变量

```sh
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY 等
```

### 3. 启动服务

```sh
python run.py
```

启动后访问：`http://localhost:8080`

- API 文档（Swagger）：`http://localhost:8080/docs`
- ReDoc：`http://localhost:8080/redoc`

## 测试账号

首次启动会自动初始化种子数据，包含以下测试账号（密码均为 `123456`）：

| 用户名 | 昵称 | 角色 |
| --- | --- | --- |
| `admin` | 管理员 | admin |
| `user` | 普通用户 | user |
| `demo` | Demo | user |

同时会初始化常见朝代（先秦至清）与作者（李白、杜甫、苏轼等）数据。

## 定时任务

后台调度器（APScheduler）随应用启动，执行以下任务：

| 任务 | 周期 | 说明 |
| --- | --- | --- |
| 清算注销用户 | 每日 02:00 | 物理删除注销超 30 天的用户及其数据 |
| 超时资源处理 | 每小时 | processing 状态超 1 小时转为 failed |
| 数据库备份 | 每日 03:00 | 备份 SQLite，保留近 7 份 |

## 文件存储

- 上传文件存放于项目根目录 `uploads/`，通过 `/uploads/<文件名>` 访问
- 数据库备份存放于 `backups/`

## 安全加固

本项目已接入以下安全机制：

- **安全响应头中间件**（`middleware/security.py`）：自动添加 XSS 防护、`X-Frame-Options`、`Content-Security-Policy` 等响应头
- **输入清洗**：登录/注册/资料更新接口对用户输入进行 HTML 转义与长度限制，防 XSS
- **速率限制**（slowapi）：登录/注册接口独立限流，全局默认限流
- **Refresh Token 机制**：登录返回 `refreshToken`，可通过 `POST /api/auth/refresh` 刷新 access_token
- **文件魔数校验**：上传接口校验文件真实类型（魔数），防止伪造扩展名攻击
- **启动安全校验**：应用启动时检查 `SECRET_KEY` / `DASHSCOPE_API_KEY` / `CORS_ORIGINS` 配置

## 部署提示

生产部署时请务必在 `.env` 中配置：

```ini
# 限制为前端域名（必填！）
CORS_ORIGINS=https://your-frontend-domain.com

# JWT 密钥至少 16 字符（必填！）
SECRET_KEY=openssl-rand-hex-32-or-later
```

## 相关说明

- 识别服务仅依赖千问 API，无本地降级模拟；API Key 未配置或失败将直接抛出异常
- CORS 来源由 `CORS_ORIGINS` 配置控制，生产环境务必收紧为前端域名