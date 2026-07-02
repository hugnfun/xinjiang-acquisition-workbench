import shutil
from pathlib import Path
from sidecar.jobs import scrape as sc
from sidecar.db.session import get_session, init_db
from sidecar.db.models import ScrapeJob, Material

FIXTURE = Path(__file__).parent / "fixtures" / "import_root" / "01_测试"
URL = "https://www.xiaohongshu.com/search_result/abc?xsec_token=tok&xsec_source="


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    init_db()


def _fake_download(url, output):
    """模拟 opencli download：把 fixture 的 note.md + images 复制到 output 目录。"""
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURE / "note.md", out / "note.md")
    (out / "images").mkdir(exist_ok=True)
    for img in (FIXTURE / "images").glob("*"):
        shutil.copy2(img, out / "images" / img.name)
    return {"ok": True}


def test_run_scrape_job_imports_note(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(sc.runner, "search", lambda kw, limit=20: [{
        "url": URL, "title": "测试标题", "author": "测试作者",
        "author_url": "u", "likes": "30",
    }])
    monkeypatch.setattr(sc.runner, "download", _fake_download)

    s = get_session()
    job = ScrapeJob(type="scrape", status="queued", params={"keyword": "x", "limit": 1})
    s.add(job); s.commit()
    sc.run_scrape_job(job.id, "x", 1)

    s2 = get_session()
    j = s2.query(ScrapeJob).get(job.id)
    assert j.status == "done"
    assert j.result_summary == {"imported": 1, "failed": 0, "total": 1}
    mats = s2.query(Material).all()
    assert len(mats) == 1
    assert mats[0].title == "测试标题"
    assert mats[0].likes == 30  # search "likes":"30" → 30
    assert len(mats[0].images) == 2


def test_run_scrape_job_download_failure_skips_and_completes(tmp_path, monkeypatch):
    """单条 download 失败不整体失败，job 仍 done。"""
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(sc.runner, "search", lambda kw, limit=20: [{"url": URL, "title": "x"}])

    def boom(url, output):
        raise RuntimeError("network down")
    monkeypatch.setattr(sc.runner, "download", boom)

    s = get_session()
    job = ScrapeJob(type="scrape", status="queued", params={"keyword": "x", "limit": 1})
    s.add(job); s.commit()
    sc.run_scrape_job(job.id, "x", 1)

    s2 = get_session()
    j = s2.query(ScrapeJob).get(job.id)
    assert j.status == "done"
    assert j.result_summary["imported"] == 0
    assert j.result_summary["failed"] == 1
    assert s2.query(Material).count() == 0
