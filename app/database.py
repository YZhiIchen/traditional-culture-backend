"""
数据库引擎 + Session 工厂
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI 依赖注入：每次请求一个 db session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _seed_data()


def _seed_data():
    """预建测试账号"""
    from sqlalchemy import select
    from .models import User

    db = SessionLocal()
    try:
        # 检查是否已有用户
        existing = db.execute(select(User).limit(1)).scalar()
        if existing:
            return  # 已有数据，跳过

        import bcrypt
        pwd = bcrypt.hashpw(b'123456', bcrypt.gensalt()).decode()

        users = [
            User(username='admin',   nickname='管理员', password_hash=pwd, role='admin', bio='平台管理员'),
            User(username='user',    nickname='普通用户', password_hash=pwd, role='user', bio='传统文化爱好者'),
            User(username='demo',    nickname='Demo',    password_hash=pwd, role='user', bio='测试用户'),
        ]
        db.add_all(users)
        db.commit()
        print('[Seed] 已创建 3 个测试账号 (admin/user/demo, 密码均为 123456)')
    except Exception as e:
        print(f'[Seed] 跳过: {e}')
    finally:
        db.close()
