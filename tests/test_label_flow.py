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
