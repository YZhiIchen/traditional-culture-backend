"""
AI 智能问答助手 — 基于 DeepSeek API 的传统文化知识问答
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
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


class ChatMessage(BaseModel):
    role: str  # user / assistant
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


@router.post("")
def chat(
    req: ChatRequest,
    current_user: Annotated[User, Depends(require_user)],
):
    """AI 智能问答 — 支持上下文记忆"""
    if not DASHSCOPE_API_KEY or len(DASHSCOPE_API_KEY) < 10:
        return fail(500, "AI 问答服务未配置 API Key")

    # 构建消息列表
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in req.history:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": req.message})

    try:
        import requests
        resp = requests.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
            headers={
                "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "qwen-plus",
                "input": {"messages": messages},
                "parameters": {
                    "result_format": "message",
                    "temperature": 0.7,
                    "max_tokens": 1500,
                    "top_p": 0.9,
                }
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        output = data.get("output", {})
        choices = output.get("choices", [])
        if choices:
            reply = choices[0].get("message", {}).get("content", "")
            return success({"reply": reply})
        return fail(500, "AI 未返回有效回答")

    except Exception as e:
        return fail(500, f"AI 问答调用失败：{str(e)}")
