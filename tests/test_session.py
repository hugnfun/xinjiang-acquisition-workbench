"""session_scope 契约：成功 commit、异常 rollback、退出即 close。"""
from sidecar.db.session import session_scope, init_db
from sidecar.db.models import Base, ScrapeJob
from sqlalchemy.orm import declarative_base


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    init_db()


def test_session_scope_commits_on_success(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with session_scope() as s:
        s.add(ScrapeJob(type="question_pool", status="queued", params={}))
    # 退出后应已持久化（新 session 可见）
    with session_scope() as s:
        assert s.query(ScrapeJob).count() == 1


def test_session_scope_rolls_back_on_exception(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    try:
        with session_scope() as s:
            s.add(ScrapeJob(type="question_pool", status="queued", params={}))
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    # 异常 → rollback，未持久化
    with session_scope() as s:
        assert s.query(ScrapeJob).count() == 0
