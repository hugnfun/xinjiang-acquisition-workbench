from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sidecar import config

# 缓存 engine/sessionmaker，按 DB_PATH 字符串作 key 失效。
_engine = None
_cached_db_path = None
_SessionLocal = None


def get_engine():
    """返回缓存的全局 engine；当 config.DB_PATH 变化时失效重建。"""
    global _engine, _cached_db_path, _SessionLocal
    config.ensure_dirs()
    current = str(config.DB_PATH)
    if _engine is None or _cached_db_path != current:
        # 连接池加大 + 长超时：长 job（问题池/打标）在后台线程持有 session 较久，
        # 同时 FastAPI 线程池的 HTTP 请求也要连接。默认 pool size 5+overflow 10
        # 会被长 job 占满 → QueuePool 超时 → HTTP /jobs 卡死、job 也拿不到连接
        # (sqlalchemy.exc.TimeoutError: QueuePool limit reached)。
        # 加大到 20+50，超时 60s，给长 job 与 HTTP 共存留余量。
        _engine = create_engine(
            f"sqlite:///{config.DB_PATH}", echo=False,
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=QueuePool,
            pool_size=20, max_overflow=50, pool_timeout=60, pool_recycle=3600,
        )
        _cached_db_path = current
        _SessionLocal = sessionmaker(bind=_engine)
    return _engine


def get_session() -> Session:
    get_engine()
    return _SessionLocal()


def init_db():
    from sidecar.db import models  # noqa: F401
    models.Base.metadata.create_all(get_engine())
