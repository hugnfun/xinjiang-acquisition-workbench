from sidecar.db.models import ScrapeJob
from sidecar.db.session import get_session
from sidecar.jobs.usage import job_usage_accumulator


def test_job_usage_is_persisted_after_each_call(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "usage.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    from sidecar.db.session import init_db
    init_db()
    with get_session() as s:
        job = ScrapeJob(type="report", status="running", params={})
        s.add(job)
        s.commit()
        job_id = job.id

    usage = job_usage_accumulator(job_id)
    usage.add_usage(100, 20, 120)
    with get_session() as s:
        saved = s.get(ScrapeJob, job_id).token_usage
        assert saved["prompt_tokens"] == 100
        assert saved["completion_tokens"] == 20
        assert saved["total_tokens"] == 120

    usage.add_usage(40, 10, 50)
    with get_session() as s:
        saved = s.get(ScrapeJob, job_id).token_usage
        assert saved["prompt_tokens"] == 140
        assert saved["total_tokens"] == 170
