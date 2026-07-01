import scripts.seed_taxonomy as seed
import scripts.import_from_folder as imp
from sidecar.jobs import label as labeljob

def test_run_label_job_writes_tags(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")

    def fake_label(title, content, image_paths, taxonomy):
        return [
            {"dimension": "content_type", "value": "风景震撼", "confidence": 0.9, "out_of_taxonomy": False},
            {"dimension": "content_type", "value": "绝美日出", "confidence": 0.5, "out_of_taxonomy": True},
        ]
    monkeypatch.setattr(labeljob, "label_material", fake_label)

    from sidecar.db.session import get_session
    from sidecar.db.models import ScrapeJob
    s = get_session()
    job = ScrapeJob(type="label_batch", status="queued", params={})
    s.add(job); s.commit()

    labeljob.run_label_job(job.id)

    from sidecar.db.models import MaterialTag, TagSuggestion
    s2 = get_session()
    assert s2.query(MaterialTag).count() >= 1
    assert s2.query(MaterialTag).filter_by(confirmed_by_human=False).count() >= 1
    assert s2.query(TagSuggestion).filter_by(status="pending").count() == 1
    job = s2.query(ScrapeJob).get(job.id)
    assert job.status == "done"

from pathlib import Path


def test_run_label_job_marks_failed_when_all_fail(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")

    def fake_label(*a):
        raise RuntimeError("boom")
    monkeypatch.setattr(labeljob, "label_material", fake_label)

    from sidecar.db.session import get_session
    from sidecar.db.models import ScrapeJob, JobLog
    s = get_session()
    job = ScrapeJob(type="label_batch", status="queued", params={})
    s.add(job); s.commit()

    labeljob.run_label_job(job.id)

    s2 = get_session()
    job = s2.query(ScrapeJob).get(job.id)
    # 全部素材打标失败时必须暴露为 failed（而非伪装 done+0）
    assert job.status == "failed"
    assert job.error
    assert "boom" in job.error
    assert "失败" in job.error
    assert job.result_summary["failed_count"] >= 1
    # 每篇素材都应有一条 error 级日志
    err_logs = s2.query(JobLog).filter_by(job_id=job.id, level="error").all()
    assert len(err_logs) >= 1


def test_source_propagated_to_material_tag(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")

    def fake_label(title, content, image_paths, taxonomy):
        return [
            {"dimension": "content_type", "value": "风景震撼", "confidence": 0.9, "out_of_taxonomy": False, "source": "ai_text"},
            {"dimension": "content_type", "value": "测试视觉标签", "confidence": 0.8, "out_of_taxonomy": True, "source": "ai_vision"},
        ]
    monkeypatch.setattr(labeljob, "label_material", fake_label)

    from sidecar.db.session import get_session
    from sidecar.db.models import ScrapeJob, MaterialTag
    s = get_session()
    job = ScrapeJob(type="label_batch", status="queued", params={})
    s.add(job); s.commit()

    labeljob.run_label_job(job.id)

    s2 = get_session()
    tags = s2.query(MaterialTag).all()
    # 风景震撼是 in-taxonomy → MaterialTag，source=ai_text
    mt = [t for t in tags]
    assert any(t.source == "ai_text" for t in mt), f"expected ai_text source, got {[t.source for t in mt]}"
