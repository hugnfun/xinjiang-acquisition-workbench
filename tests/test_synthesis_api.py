from fastapi.testclient import TestClient
import scripts.seed_taxonomy as seed
import scripts.import_from_folder as imp
from sidecar.db.session import get_session
from sidecar.db.models import Asset
from sidecar.app import create_app
from pathlib import Path

def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")
    return TestClient(create_app())

def test_list_assets(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    s.add(Asset(type="selling_point", text="纯玩", derived_from=[1], tags=[]))
    s.commit()
    r = client.get("/assets?type=selling_point")
    assert r.status_code == 200
    assert len(r.json()) >= 1

def test_delete_asset(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    a = Asset(type="hook", text="x", derived_from=[], tags=[])
    s.add(a); s.commit(); s.refresh(a)
    aid = a.id
    s.close()
    r = client.delete(f"/assets/{aid}")
    assert r.status_code == 200
    s2 = get_session()
    assert s2.query(Asset).get(aid) is None

def test_dislike_asset(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    a = Asset(type="cta", text="x", derived_from=[], tags=[])
    s.add(a); s.commit(); s.refresh(a)
    aid = a.id
    s.close()
    r = client.put(f"/assets/{aid}", json={"disliked": True})
    assert r.status_code == 200
    s2 = get_session()
    assert s2.query(Asset).get(aid).disliked is True


def test_extract_uses_job_queue(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        "sidecar.api.synthesis.submit",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    s = get_session()
    mid = s.query(Asset).count() + 1
    s.close()
    r = client.post(
        "/synthesis/extract",
        json={"material_ids": [mid], "types": ["title"]},
    )
    assert r.status_code == 200
    jid = r.json()["job_id"]
    assert calls and calls[0][0][0] == jid
    assert calls[0][0][2:] == ([mid], ["title"], jid)
