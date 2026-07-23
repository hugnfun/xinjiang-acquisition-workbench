import threading

import pytest

from sidecar.db.models import ScrapeJob
from sidecar.db.session import get_session, init_db, session_scope
from sidecar.jobs.queue import submit


def _jobs(tmp_path, monkeypatch, count=1):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "queue.db")
    init_db()
    with session_scope() as s:
        rows = [
            ScrapeJob(type="test", status="queued", params={})
            for _ in range(count)
        ]
        s.add_all(rows)
        s.flush()
        return [row.id for row in rows]


def test_queue_is_serial_and_skips_cancelled_work(tmp_path, monkeypatch):
    first_id, second_id = _jobs(tmp_path, monkeypatch, 2)
    entered = threading.Event()
    release = threading.Event()
    events = []

    def first():
        events.append("first:start")
        entered.set()
        assert release.wait(2)
        events.append("first:end")

    def second():
        events.append("second")

    first_handle = submit(first_id, first)
    assert entered.wait(2)
    second_handle = submit(second_id, second)
    with session_scope() as s:
        second_job = s.get(ScrapeJob, second_id)
        second_job.status = "cancelled"
    release.set()

    first_handle.result(2)
    second_handle.result(2)
    assert events == ["first:start", "first:end"]

    s = get_session()
    assert s.get(ScrapeJob, first_id).status == "done"
    assert s.get(ScrapeJob, second_id).status == "cancelled"
    s.close()


def test_queue_marks_unhandled_exception_failed(tmp_path, monkeypatch):
    [job_id] = _jobs(tmp_path, monkeypatch)

    def explode():
        raise RuntimeError("queue boom")

    handle = submit(job_id, explode)
    with pytest.raises(RuntimeError, match="queue boom"):
        handle.result(2)

    s = get_session()
    job = s.get(ScrapeJob, job_id)
    assert job.status == "failed"
    assert job.error == "queue boom"
    assert job.finished_at is not None
    s.close()
