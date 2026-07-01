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
