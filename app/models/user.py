"""
用户模型
"""
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), default=None)
    bio: Mapped[str | None] = mapped_column(String(500), default=None)
    role: Mapped[str] = mapped_column(String(20), default="user")  # user / researcher / admin

    avatar: Mapped[str | None] = mapped_column(String(500), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    # 关联：一个用户有多个上传的资源
    resources = relationship("Resource", back_populates="owner")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "nickname": self.nickname,
            "email": self.email,
            "bio": self.bio,
            "role": self.role,
            "avatar": self.avatar,
            "deleted": self.deleted_at is not None,
        }