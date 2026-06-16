"""
认证路由：登录 / 注册 / 用户信息 / 修改密码
"""
from typing import Annotated
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas.auth import LoginRequest, RegisterRequest, UpdateProfileRequest, ChangePasswordRequest
from ..services import auth_service
from ..utils.auth import create_access_token, require_user
from ..utils.response import success, fail

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
def login(data: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    """用户登录"""
    user = auth_service.authenticate(db, data.username, data.password)
    if not user:
        return fail(401, "用户名或密码错误")
    token = create_access_token(user.id)
    return success({
        "token": token,
        "userInfo": user.to_dict(),
    })


@router.post("/register")
def register(data: RegisterRequest, db: Annotated[Session, Depends(get_db)]):
    """用户注册"""
    try:
        result = auth_service.register_user(db, data)
        return success(result, "注册成功")
    except ValueError as e:
        return fail(400, str(e))


@router.post("/logout")
def logout():
    """退出登录（JWT 无状态，前端清 token 即可）"""
    return success(None, "已退出")


# ── 用户相关接口放在 /user 前缀下 ──

user_router = APIRouter(prefix="/user", tags=["用户"])


@user_router.get("/info")
def get_user_info(current_user: Annotated[User, Depends(require_user)]):
    """获取当前用户信息"""
    return success(current_user.to_dict())


@user_router.put("/profile")
def update_profile(
    data: UpdateProfileRequest,
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """更新个人信息"""
    result = auth_service.update_profile(db, current_user, data)
    return success(result, "更新成功")


@user_router.delete("/account")
def delete_account(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """注销账号（软删除，保留30天）"""
    from datetime import datetime
    current_user.deleted_at = datetime.now()
    current_user.nickname = "已注销用户"
    db.commit()
    return success(None, "账号已注销，数据将保留30天后清除")


@user_router.put("/password")
def change_password(
    data: ChangePasswordRequest,
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """修改密码"""
    try:
        auth_service.change_password(db, current_user, data)
        return success(None, "密码已修改")
    except ValueError as e:
        return fail(400, str(e))


@user_router.post("/avatar")
def upload_avatar(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """上传头像"""
    import uuid
    from pathlib import Path as P
    from ..config import UPLOAD_DIR

    avatar_dir = UPLOAD_DIR / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)

    ext = P(file.filename).suffix if file.filename else ".jpg"
    save_name = f"avatar_{current_user.id}{ext}"
    save_path = avatar_dir / save_name

    content = file.file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    current_user.avatar = f"/uploads/avatars/{save_name}"
    db.commit()
    return success({"avatar": current_user.avatar}, "头像已更新")


# ── 管理接口（仅 admin 角色可用）──

@user_router.get("/list")
def list_users(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """获取用户列表（仅 admin）"""
    if current_user.role != "admin":
        return fail(403, "无权限")
    users = db.query(User).all()
    return success([u.to_dict() for u in users])
