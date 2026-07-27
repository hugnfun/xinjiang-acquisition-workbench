from fastapi.testclient import TestClient

from sidecar.app import create_app
from sidecar.db.models import Material
from sidecar.db.session import get_session


def test_backfill_authors_api_preview_then_execute(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "api.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text(
        "正文\n共 1 条评论\n\n领队多多\n作者\n置顶评论\n欢迎咨询\n"
        "2025-05-02新疆\n赞\n回复\n",
        encoding="utf-8",
    )
    client = TestClient(create_app())
    with get_session() as s:
        s.add(Material(
            note_id="api-author", url="", title="note", author="",
            content="正文", platform="xiaohongshu",
            local_folder="workvault:note.md",
        ))
        s.commit()

    preview = client.post("/work-vault/backfill-authors", json={
        "vault_dir": str(vault), "dry_run": True,
    })
    assert preview.status_code == 200
    assert preview.json()["repairable"] == 1
    with get_session() as s:
        assert s.query(Material).filter_by(note_id="api-author").one().author == ""

    executed = client.post("/work-vault/backfill-authors", json={
        "vault_dir": str(vault), "dry_run": False,
    })
    assert executed.status_code == 200
    assert executed.json()["updated"] == 1
    with get_session() as s:
        assert s.query(Material).filter_by(note_id="api-author").one().author == "领队多多"
