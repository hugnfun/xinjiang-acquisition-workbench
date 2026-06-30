from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sidecar import config

def get_engine():
    config.ensure_dirs()
    return create_engine(f"sqlite:///{config.DB_PATH}", echo=False)

def get_session() -> Session:
    return sessionmaker(bind=get_engine())()

def init_db():
    from sidecar.db import models  # noqa: F401
    models.Base.metadata.create_all(get_engine())
