from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from sidecar.app import create_app
from sidecar.db.models import Asset
from sidecar.db.session import get_session


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "experiments.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    client = TestClient(create_app())
    with get_session() as s:
        assets = [
            Asset(type="title", text="新疆标题", derived_from=[], tags=[]),
            Asset(type="hook", text="先别急着报团", derived_from=[], tags=[]),
            Asset(type="cta", text="私信定制", derived_from=[], tags=[]),
        ]
        s.add_all(assets)
        s.commit()
        ids = [a.id for a in assets]
    return client, ids


def _create(client, asset_ids):
    r = client.post("/experiments", json={
        "asset_ids": asset_ids,
        "final_title": "新疆标题",
        "final_body": "先别急着报团\n\n私信定制",
        "target_audience": "亲子家庭",
    })
    assert r.status_code == 200, r.text
    return r.json()


def _publish(client, experiment_id, url="https://xhs.example/note/1"):
    r = client.put(f"/experiments/{experiment_id}", json={
        "status": "published",
        "published_url": url,
        "published_at": "2026-07-28T10:00:00",
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_create_snapshots_assets_and_marks_adopted(tmp_path, monkeypatch):
    client, asset_ids = _setup(tmp_path, monkeypatch)
    experiment = _create(client, asset_ids)
    assert experiment["status"] == "draft"
    assert [a["asset_id"] for a in experiment["assets"]] == asset_ids
    assert experiment["assets"][0]["text_snapshot"] == "新疆标题"
    with get_session() as s:
        assert {s.get(Asset, aid).status for aid in asset_ids} == {"adopted"}


def test_publish_validation_transition_and_asset_status(tmp_path, monkeypatch):
    client, asset_ids = _setup(tmp_path, monkeypatch)
    experiment = _create(client, asset_ids)
    invalid = client.put(f"/experiments/{experiment['id']}", json={
        "status": "published",
    })
    assert invalid.status_code == 400
    published = _publish(client, experiment["id"])
    assert published["status"] == "published"
    with get_session() as s:
        assert {s.get(Asset, aid).status for aid in asset_ids} == {"published"}
    backwards = client.put(f"/experiments/{experiment['id']}", json={
        "status": "draft",
    })
    assert backwards.status_code == 409
    archived = client.put(f"/experiments/{experiment['id']}", json={
        "status": "archived",
    })
    assert archived.status_code == 200


def test_duplicate_publish_url_rejected(tmp_path, monkeypatch):
    client, asset_ids = _setup(tmp_path, monkeypatch)
    first = _create(client, [asset_ids[0]])
    _publish(client, first["id"])
    second = _create(client, [asset_ids[1]])
    r = client.put(f"/experiments/{second['id']}", json={
        "status": "published",
        "published_url": "https://xhs.example/note/1",
        "published_at": "2026-07-28T11:00:00",
    })
    assert r.status_code == 409


def test_metrics_require_published_and_validate_nonnegative(tmp_path, monkeypatch):
    client, asset_ids = _setup(tmp_path, monkeypatch)
    experiment = _create(client, asset_ids)
    blocked = client.post(f"/experiments/{experiment['id']}/metrics", json={
        "views": 10,
    })
    assert blocked.status_code == 409
    _publish(client, experiment["id"])
    invalid = client.post(f"/experiments/{experiment['id']}/metrics", json={
        "views": -1,
    })
    assert invalid.status_code == 422
    created = client.post(f"/experiments/{experiment['id']}/metrics", json={
        "measured_at": "2026-07-29T10:00:00",
        "views": 100,
        "likes": 10,
        "inquiries": 4,
        "wechat_adds": 2,
        "orders": 1,
        "revenue_cents": 300000,
    })
    assert created.status_code == 200
    sid = created.json()["id"]
    updated = client.put(
        f"/experiments/{experiment['id']}/metrics/{sid}",
        json={"views": 90, "notes": "平台修正"},
    )
    assert updated.status_code == 200
    assert updated.json()["views"] == 90


def test_analytics_uses_latest_snapshot_only(tmp_path, monkeypatch):
    client, asset_ids = _setup(tmp_path, monkeypatch)
    experiment = _create(client, asset_ids)
    _publish(client, experiment["id"])
    endpoint = f"/experiments/{experiment['id']}/metrics"
    assert client.post(endpoint, json={
        "measured_at": "2026-07-29T10:00:00",
        "views": 100, "likes": 10, "inquiries": 2,
    }).status_code == 200
    assert client.post(endpoint, json={
        "measured_at": "2026-07-30T10:00:00",
        "views": 250, "likes": 30, "collects": 10,
        "inquiries": 5, "wechat_adds": 3, "orders": 1,
    }).status_code == 200
    data = client.get("/experiments/analytics").json()
    assert data["published_count"] == 1
    assert data["views"] == 250
    assert data["engagements"] == 40
    assert data["inquiry_rate"] == 0.02
    assert data["wechat_rate"] == 0.6
    assert data["ranking"][0]["experiment_id"] == experiment["id"]


def test_asset_delete_preserves_experiment_snapshot(tmp_path, monkeypatch):
    client, asset_ids = _setup(tmp_path, monkeypatch)
    experiment = _create(client, [asset_ids[0]])
    assert client.delete(f"/assets/{asset_ids[0]}").status_code == 200
    detail = client.get(f"/experiments/{experiment['id']}").json()
    assert detail["assets"][0]["asset_id"] is None
    assert detail["assets"][0]["text_snapshot"] == "新疆标题"


def test_list_filters_and_paginates(tmp_path, monkeypatch):
    client, asset_ids = _setup(tmp_path, monkeypatch)
    _create(client, [asset_ids[0]])
    second = _create(client, [asset_ids[1]])
    _publish(client, second["id"], "https://xhs.example/note/2")
    drafts = client.get("/experiments?status=draft&limit=1").json()
    assert drafts["total"] == 1
    assert len(drafts["items"]) == 1
