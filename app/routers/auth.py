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
    user, deleted = auth_service.authenticate(db, data.username, data.password)
    if not user:
        return fail(401, "用户名或密码错误")
    if deleted:
        return success({
            "deleted": True,
            "username": user.username,
        }, "该账号已注销，是否恢复？")
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
    """更新个人信息（需审核，当前直接通过）"""
    from ..services.review_service import review_profile

    review_result = review_profile(current_user.id, data.nickname, data.email or "", data.bio or "")
    if not review_result["approved"]:
        return fail(400, f"资料审核未通过：{review_result['reason']}")

    result = auth_service.update_profile(db, current_user, data)
    return success(result, "更新成功")


@user_router.delete("/account")
def delete_account(
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """注销账号（软删除，保留30天）"""
    from datetime import datetime
    from pathlib import Path as P
    from ..config import UPLOAD_DIR

    # 删除用户头像物理文件
    if current_user.avatar:
        try:
            fp = UPLOAD_DIR / "headportrait" / P(current_user.avatar).name
            if fp.exists():
                fp.unlink(missing_ok=True)
        except Exception:
            pass
        current_user.avatar = None

    current_user.deleted_at = datetime.now()
    db.commit()
    return success(None, "账号已注销，数据将保留30天后清除")


@user_router.post("/reactivate")
def reactivate_account(
    data: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """恢复已注销账号"""
    user, deleted = auth_service.authenticate(db, data.username, data.password)
    if not user:
        return fail(401, "用户名或密码错误")
    if not deleted:
        return fail(400, "该账号未注销，无需恢复")
    result = auth_service.reactivate_user(db, user)
    return success(result, "账号已恢复")


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
    """上传头像（需审核，当前直接通过）"""
    from pathlib import Path as P
    from ..config import UPLOAD_DIR
    from ..services.review_service import review_avatar

    avatar_dir = UPLOAD_DIR / "headportrait"
    avatar_dir.mkdir(parents=True, exist_ok=True)

    ext = P(file.filename).suffix if file.filename else ".png"
    save_name = f"avatar_{current_user.id}{ext}"
    save_path = avatar_dir / save_name

    content = file.file.read()
    if not content or len(content) < 100:
        return fail(400, "头像文件为空或损坏")

    with open(save_path, "wb") as f:
        f.write(content)

    avatar_url = f"/uploads/headportrait/{save_name}"

    # 审核机制（当前模拟直接通过，预留接口）
    review_result = review_avatar(current_user.id, avatar_url, content)
    if not review_result["approved"]:
        P(save_path).unlink(missing_ok=True)
        return fail(400, f"头像审核未通过：{review_result['reason']}")

    current_user.avatar = avatar_url
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