from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, event
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
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(
            f"sqlite:///{config.DB_PATH}", echo=False,
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=QueuePool,
            pool_size=8, max_overflow=8, pool_timeout=30, pool_recycle=3600,
        )

        @event.listens_for(_engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        _cached_db_path = current
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session() -> Session:
    get_engine()
    return _SessionLocal()


def get_db():
    """FastAPI 请求级 session：无论成功或异常都保证释放连接。"""
    s = get_session()
    try:
        yield s
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


@contextmanager
def session_scope():
    """短生命周期 session：成功 commit、异常 rollback、退出即 close。

    长 job（问题池/打标/合成）在 LLM/MiniMax/embedding 调用期间不得持有 session——
    会与 FastAPI HTTP 线程争抢共享连接池导致 /jobs 卡死。改用本上下文：每个 DB
    操作单元开一个短 session，LLM 调用前关闭，不长期占连接。
    注意：commit 后 ORM 对象属性会 expire，需在 session 关闭前把要用到的标量
    提取到普通 dict/tuple，否则访问会触发 DetachedInstanceError。
    """
    s = get_session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db():
    from sidecar.db import models  # noqa: F401
    models.Base.metadata.create_all(get_engine())
    run_migrations()


def run_migrations():
    """把空库和历史 create_all 数据库统一升级到最新 Alembic 版本。"""
    from alembic import command
    from alembic.config import Config

    ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    with get_engine().begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.upgrade(alembic_cfg, "head")
