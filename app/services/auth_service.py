"""
用户认证服务
"""
import bcrypt
from sqlalchemy.orm import Session

from ..models import User
from ..schemas.auth import RegisterRequest, UpdateProfileRequest, ChangePasswordRequest
from ..utils.auth import create_access_token


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def authenticate(db: Session, username: str, password: str):
    """验证用户名密码，返回 (user, deleted) 元组。
    deleted=True 表示账号已注销但仍在 30 天保留期内。"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None, False
    return user, user.deleted_at is not None


def register_user(db: Session, data: RegisterRequest) -> tuple[dict, User]:
    """注册新用户，返回 (result_dict, user_object)"""
    # 检查用户名唯一
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise ValueError("用户名已存在")

    user = User(
        username=data.username,
        nickname=data.nickname,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.token_version)
    return {
        "token": token,
        "userInfo": user.to_dict(),
    }, user


def get_profile(user: User) -> dict:
    return user.to_dict()


def update_profile(db: Session, user: User, data: UpdateProfileRequest) -> dict:
    if data.nickname is not None:
        user.nickname = data.nickname
    if data.email is not None:
        user.email = data.email
    if data.bio is not None:
        user.bio = data.bio
    db.commit()
    db.refresh(user)
    return user.to_dict()


def reactivate_user(db: Session, user: User) -> dict:
    """恢复已注销账号：清空注销标记，还原完整信息"""
    user.deleted_at = None
    # 递增 token_version，使旧会话失效
    user.token_version += 1
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.token_version)
    return {
        "token": token,
        "userInfo": user.to_dict(),
    }


def change_password(db: Session, user: User, data: ChangePasswordRequest) -> None:
    if not verify_password(data.current, user.password_hash):
        raise ValueError("当前密码不正确")
    user.password_hash = hash_password(data.newPwd)
    # 修改密码后递增 token_version，使所有旧会话失效
    user.token_version += 1
    db.commit()