from fastapi.testclient import TestClient
import scripts.import_from_folder as imp
import scripts.seed_taxonomy as seed
from sidecar.app import create_app

def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")
    return TestClient(create_app())

from pathlib import Path

def test_list_materials(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.get("/materials")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "测试标题"

def test_get_material_detail(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    mid = client.get("/materials").json()["items"][0]["id"]
    r = client.get(f"/materials/{mid}")
    assert r.status_code == 200
    assert "content" in r.json()
    assert len(r.json()["images"]) == 2

def test_list_tags(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.get("/tags")
    assert r.status_code == 200
    names = {d["name"] for d in r.json()}
    assert "content_type" in names

def test_merge_suggestion_persists_alias(tmp_path, monkeypatch):
    from sidecar.db.session import get_session
    from sidecar.db.models import TagDimension, TagValue, TagSuggestion
    client = _setup(tmp_path, monkeypatch)
    # Seed a pending suggestion targeting an existing TagValue (alias starts [])
    s = get_session()
    d = s.query(TagDimension).filter_by(name="content_type").first()
    tv = d.values[0]
    sg = TagSuggestion(dimension_name="content_type", proposed_value="新别名",
                       material_id=None, sample_context="ctx", status="pending")
    s.add(sg); s.commit()
    sg_id, tv_id = sg.id, tv.id
    s.close()
    r = client.post(f"/tags/suggestions/{sg_id}",
                    json={"action": "merge", "merge_into_value_id": tv_id})
    assert r.status_code == 200
    # Fresh session: alias MUST contain proposed_value, suggestion merged
    s2 = get_session()
    tv2 = s2.query(TagValue).get(tv_id)
    assert "新别名" in tv2.alias
    sg2 = s2.query(TagSuggestion).get(sg_id)
    assert sg2.status == "merged"
    s2.close()

def test_get_job_missing_returns_404(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.get("/jobs/999999")
    assert r.status_code == 404
