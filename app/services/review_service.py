"""
传统文化数字化平台 — 内容审核服务

当前为模拟实现：所有提交直接通过审核。
预留接口，后期可接入真实审核（敏感词、图像识别、人工审核等）。
"""
from typing import Tuple, Dict, Any


def review_avatar(user_id: int, avatar_url: str, content: bytes) -> Dict[str, Any]:
    """
    审核用户头像

    Args:
        user_id: 用户 ID
        avatar_url: 头像访问 URL
        content: 头像文件二进制内容

    Returns:
        {"approved": bool, "reason": str}
    """
    # TODO: 后期接入真实审核（图像内容识别、违规检测等）
    # 当前模拟：直接通过
    return {"approved": True, "reason": ""}


def review_nickname(user_id: int, nickname: str) -> Dict[str, Any]:
    """
    审核用户昵称

    Args:
        user_id: 用户 ID
        nickname: 新昵称

    Returns:
        {"approved": bool, "reason": str}
    """
    # TODO: 后期接入敏感词过滤、违规昵称检测
    # 当前模拟：直接通过
    return {"approved": True, "reason": ""}


def review_profile(user_id: int, nickname: str, email: str, bio: str) -> Dict[str, Any]:
    """
    审核用户资料修改

    Args:
        user_id: 用户 ID
        nickname: 昵称
        email: 邮箱
        bio: 简介

    Returns:
        {"approved": bool, "reason": str}
    """
    # TODO: 后期接入综合审核
    # 当前模拟：直接通过
    return {"approved": True, "reason": ""}