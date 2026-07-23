"""数据库生命周期、迁移和 SQLite 可靠性契约。"""
import sqlite3

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from sidecar.db.session import get_db, get_engine, session_scope, init_db
from sidecar.db.models import Material, ScrapeJob


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


def test_request_dependency_closes_session(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    dependency = get_db()
    s = next(dependency)
    dependency.close()
    assert s.is_active
    assert s.get_bind() is not None
    # close 后再次使用会按需建立新事务，但之前检出的连接已归还连接池。
    assert get_engine().pool.checkedout() == 0


def test_sqlite_pragmas_are_enabled(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with get_engine().connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 30000


def test_legacy_database_is_migrated(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE material (
          id INTEGER PRIMARY KEY, platform VARCHAR(32), note_id VARCHAR(64),
          url TEXT, title TEXT, author VARCHAR(128), content TEXT,
          likes INTEGER, collects INTEGER, comments_count INTEGER,
          tags_raw TEXT, published_at VARCHAR(32), fetched_at DATETIME,
          local_folder TEXT
        );
        CREATE TABLE material_image (
          id INTEGER PRIMARY KEY, material_id INTEGER, idx INTEGER,
          path TEXT, type VARCHAR(16)
        );
        CREATE TABLE comment (
          id INTEGER PRIMARY KEY, material_id INTEGER, rank INTEGER,
          author VARCHAR(128), user_id VARCHAR(64), profile_url TEXT,
          text TEXT, likes INTEGER, time VARCHAR(64), is_reply BOOLEAN,
          reply_to VARCHAR(128)
        );
        CREATE TABLE tag_dimension (
          id INTEGER PRIMARY KEY, name VARCHAR(64), description TEXT
        );
        CREATE TABLE tag_value (
          id INTEGER PRIMARY KEY, dimension_id INTEGER, value VARCHAR(64),
          alias JSON, status VARCHAR(16), created_at DATETIME
        );
        CREATE TABLE material_tag (
          id INTEGER PRIMARY KEY, material_id INTEGER, tag_value_id INTEGER,
          source VARCHAR(16), confidence FLOAT, confirmed_by_human BOOLEAN,
          confirmed_at DATETIME
        );
        CREATE TABLE tag_suggestion (
          id INTEGER PRIMARY KEY, dimension_name VARCHAR(64),
          proposed_value VARCHAR(64), material_id INTEGER,
          sample_context TEXT, status VARCHAR(16), created_at DATETIME
        );
        CREATE TABLE scrape_job (
          id INTEGER PRIMARY KEY, type VARCHAR(32), status VARCHAR(16),
          params JSON, result_summary JSON, error TEXT, started_at DATETIME,
          finished_at DATETIME, created_at DATETIME
        );
        CREATE TABLE job_log (
          id INTEGER PRIMARY KEY, job_id INTEGER, level VARCHAR(16),
          message TEXT, created_at DATETIME
        );
        CREATE TABLE question_cluster (
          id INTEGER PRIMARY KEY, name VARCHAR(64), description TEXT,
          question_count INTEGER, created_at DATETIME
        );
        CREATE TABLE question (
          id INTEGER PRIMARY KEY, normalized_text TEXT, raw_text TEXT,
          source_ref INTEGER, source_type VARCHAR(32), embedding BLOB,
          cluster_id INTEGER, created_at DATETIME
        );
        CREATE TABLE asset (
          id INTEGER PRIMARY KEY, type VARCHAR(32), text TEXT,
          derived_from JSON, tags JSON, disliked BOOLEAN,
          created_at DATETIME
        );
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("sidecar.config.DB_PATH", db_path)
    init_db()

    with get_engine().connect() as migrated:
        comment_columns = {
            row[1] for row in migrated.execute(text("PRAGMA table_info(comment)"))
        }
        job_columns = {
            row[1] for row in migrated.execute(text("PRAGMA table_info(scrape_job)"))
        }
        assert {"question_status", "question_processed_at"} <= comment_columns
        assert {"progress", "progress_total", "cancel_requested"} <= job_columns
        assert migrated.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0003_asset_quality"


def test_material_identity_is_unique(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add_all([
                Material(platform="xiaohongshu", note_id="same", url="1", title="1", author="a"),
                Material(platform="xiaohongshu", note_id="same", url="2", title="2", author="b"),
            ])
