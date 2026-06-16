"""
Auth 请求/响应模型
"""
from pydantic import BaseModel, Field, EmailStr


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=6, max_length=20)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=6, max_length=20)
    nickname: str = Field(min_length=2, max_length=20)


class UpdateProfileRequest(BaseModel):
    nickname: str | None = Field(default=None, min_length=2, max_length=20)
    email: str | None = None
    bio: str | None = Field(default=None, max_length=500)


class ChangePasswordRequest(BaseModel):
    current: str = Field(min_length=6, max_length=20)
    newPwd: str = Field(min_length=6, max_length=20)
