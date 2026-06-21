"""
Search 请求/响应模型
"""
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    keyword: str = Field(default="", max_length=100)
    type: str | None = None  # image / text / all
    dynasty: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100, alias="pageSize")
