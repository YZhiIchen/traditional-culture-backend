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
    """预建测试账号 + 朝代 + 作者"""
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
        print(f'[Seed] 用户跳过: {e}')
    finally:
        db.close()

    # 种子朝代和作者（独立于用户，每次重置数据库时重新创建）
    from .models import Dynasty, Author
    db = SessionLocal()
    try:
        existing = db.execute(select(Dynasty).limit(1)).scalar()
        if existing:
            return

        dynasties = [
            Dynasty(name='先秦'), Dynasty(name='汉'), Dynasty(name='魏晋'),
            Dynasty(name='唐'), Dynasty(name='宋'), Dynasty(name='元'),
            Dynasty(name='明'), Dynasty(name='清'),
        ]
        db.add_all(dynasties)
        db.commit()

        authors = [
            Author(name='佚名'),
            Author(name='李白', dynasty='唐'), Author(name='杜甫', dynasty='唐'),
            Author(name='王维', dynasty='唐'), Author(name='白居易', dynasty='唐'),
            Author(name='苏轼', dynasty='宋'), Author(name='李清照', dynasty='宋'),
            Author(name='辛弃疾', dynasty='宋'), Author(name='欧阳修', dynasty='宋'),
            Author(name='王羲之', dynasty='魏晋'), Author(name='颜真卿', dynasty='唐'),
            Author(name='吴道子', dynasty='唐'), Author(name='张择端', dynasty='宋'),
            Author(name='黄公望', dynasty='元'), Author(name='赵孟頫', dynasty='元'),
            Author(name='董其昌', dynasty='明'), Author(name='顾恺之', dynasty='魏晋'),
            Author(name='郑板桥', dynasty='清'), Author(name='曹雪芹', dynasty='清'),
        ]
        db.add_all(authors)
        db.commit()
        print('[Seed] 已初始化朝代和作者列表')
    except Exception as e:
        print(f'[Seed] 朝代/作者跳过: {e}')
    finally:
        db.close()
