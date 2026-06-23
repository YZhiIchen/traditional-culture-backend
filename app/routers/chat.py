"""
AI 智能问答助手 — 基于通义千问 API 的传统文化知识问答

特性：
- SSE 流式输出，逐字返回
- 基于 user_id 的服务端会话隔离，每用户独立上下文
- 服务端管理会话历史，前端不可篡改
"""
import json
from collections import defaultdict, deque
from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import DASHSCOPE_API_KEY
from ..database import get_db
from ..models.user import User
from ..utils.auth import require_user
from ..utils.response import success, fail

router = APIRouter(prefix="/chat", tags=["AI问答"])

SYSTEM_PROMPT = """你是一位精通中国传统文化、古籍、文物、书画、历史的专家助手。
请用中文回答，语言简洁准确。
回答内容应基于传统文化知识，遇到不确定的内容请说明。
如果问题与传统文化无关，请礼貌引导回传统文化话题。"""

# ── 会话隔离：基于 user_id 的服务端会话历史 ──
# 每个用户维护独立的对话上下文，最多保留最近 20 条
MAX_HISTORY = 20
_sessions: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))


def _get_session(user_id: int) -> list[dict]:
    """获取指定用户的会话历史（服务端隔离）"""
    return list(_sessions[user_id])


def _append_session(user_id: int, role: str, content: str) -> None:
    """向指定用户的会话追加一条消息"""
    _sessions[user_id].append({"role": role, "content": content})


class ChatRequest(BaseModel):
    message: str


@router.post("")
def chat(
    req: ChatRequest,
    current_user: Annotated[User, Depends(require_user)],
):
    """AI 智能问答 — SSE 流式输出 + 服务端会话隔离"""
    if not DASHSCOPE_API_KEY or len(DASHSCOPE_API_KEY) < 10:
        return fail(500, "AI 问答服务未配置 API Key")

    user_msg = req.message.strip()
    if not user_msg:
        return fail(400, "消息不能为空")

    uid = current_user.id

    # 构建消息列表：system + 服务端会话历史 + 当前用户消息
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(_get_session(uid))
    messages.append({"role": "user", "content": user_msg})

    # 记录用户消息到会话
    _append_session(uid, "user", user_msg)

    def event_stream():
        """SSE 流式生成器：逐块转发通义千问的流式响应"""
        full_reply = ""
        try:
            import requests
            with requests.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                headers={
                    "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                    "Content-Type": "application/json",
                    "X-DashScope-SSE": "enable",
                },
                json={
                    "model": "qwen-plus",
                    "input": {"messages": messages},
                    "parameters": {
                        "result_format": "message",
                        "temperature": 0.7,
                        "max_tokens": 1500,
                        "top_p": 0.9,
                        "incremental_output": True,
                    },
                },
                stream=True,
                timeout=60,
            ) as resp:
                resp.raise_for_status()

                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    # DashScope SSE 格式：data:{...}
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            output = data.get("output", {})
                            choices = output.get("choices", [])
                            if choices:
                                delta = choices[0].get("message", {}).get("content", "")
                                if delta:
                                    full_reply += delta
                                    yield f"data: {json.dumps({'content': delta}, ensure_ascii=False)}\n\n"
                        except json.JSONDecodeError:
                            continue

            # 流结束，记录助手回复到会话
            if full_reply:
                _append_session(uid, "assistant", full_reply)

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/clear")
def clear_session(
    current_user: Annotated[User, Depends(require_user)],
):
    """清空当前用户的会话历史"""
    uid = current_user.id
    if uid in _sessions:
        _sessions[uid].clear()
    return success(None, "会话已清空")
