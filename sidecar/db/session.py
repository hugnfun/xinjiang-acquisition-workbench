from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sidecar import config

# 缓存 engine/sessionmaker，按 DB_PATH 字符串作 key 失效。
# 原实现每次 get_session() 都 create_engine()+sessionmaker() —— 每请求一个
# engine 的泄漏。这里改为进程内单一 engine + 单一 sessionmaker。
# 测试会 monkeypatch sidecar.config.DB_PATH 到不同 tmp 路径，故当 DB_PATH
# 变化时必须重建 engine（否则会复用到错误库的旧 engine）。
_engine = None
_cached_db_path = None
_SessionLocal = None


def get_engine():
    """返回缓存的全局 engine；当 config.DB_PATH 变化时失效重建。"""
    global _engine, _cached_db_path, _SessionLocal
    config.ensure_dirs()
    current = str(config.DB_PATH)
    if _engine is None or _cached_db_path != current:
        # check_same_thread=False：缓存后的单一 engine 会被 FastAPI 线程池
        # 与打标后台线程（asyncio.to_thread）共享，必须放宽 pysqlite 的同线程
        # 限制（SQLite 共享 engine 的标准写法）。原实现靠每请求新建 engine
        # 在各自调用线程里规避了该问题；缓存后需显式放宽。
        _engine = create_engine(
            f"sqlite:///{config.DB_PATH}", echo=False,
            connect_args={"check_same_thread": False},
        )
        _cached_db_path = current
        _SessionLocal = sessionmaker(bind=_engine)
    return _engine


def get_session() -> Session:
    get_engine()  # 确保缓存与当前 DB_PATH 一致（可能触发重建）
    return _SessionLocal()


def init_db():
    from sidecar.db import models  # noqa: F401
    models.Base.metadata.create_all(get_engine())
