"""
资源/识别结果模型
"""
import json
import ast
from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


def _parse_raw_data(raw):
    """将 raw_data 字段还原为字典，兼容历史 str(ai) 存储与新 JSON 存储"""
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        try:
            return ast.literal_eval(raw)
        except Exception:
            return None


def _extract_raw_data(raw):
    """提取原始文件数据 {content: ...}。

    raw_data 存储的是整个识别结果 ai 字典，其中 ai['rawData'] = {'content': 原始文本}。
    前端期望 rawData 直接为 {'content': ...}，故从 ai 中取出该子键。
    兼容历史数据与缺失情况。
    """
    parsed = _parse_raw_data(raw)
    if isinstance(parsed, dict) and isinstance(parsed.get("rawData"), dict):
        return parsed["rawData"]
    return parsed


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # 文件信息
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # image / text
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_url: Mapped[str | None] = mapped_column(String(500), default=None)

    # 识别结果
    status: Mapped[str] = mapped_column(String(20), default="processing")  # processing / completed / failed
    recognition_time: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    # 识别结构化数据（JSON）
    title: Mapped[str | None] = mapped_column(String(255), default=None)
    author: Mapped[str | None] = mapped_column(String(100), default=None)
    dynasty: Mapped[str | None] = mapped_column(String(20), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    tags: Mapped[str | None] = mapped_column(Text, default=None)  # 逗号分隔存储
    content: Mapped[str | None] = mapped_column(Text, default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)

    # 原始数据（JSON 字符串）
    raw_data: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="resources")

    def to_dict(self):
        return {
            "id": str(self.file_id),
            "fileId": self.file_id,
            "fileName": self.file_name,
            "fileType": self.file_type,
            "fileUrl": self.file_url,
            "status": self.status,
            "recognitionTime": self.recognition_time.isoformat() if self.recognition_time else None,
            "result": {
                "title": self.title,
                "author": self.author,
                "dynasty": self.dynasty,
                "description": self.description,
                "tags": self.tags.split(",") if self.tags else [],
                "content": self.content,
                "confidence": self.confidence,
            },
            "rawData": _extract_raw_data(self.raw_data),
        }