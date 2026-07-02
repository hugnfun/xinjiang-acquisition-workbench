from fastapi.testclient import TestClient
import scripts.seed_taxonomy as seed
from sidecar.db.session import get_session
from sidecar.db.models import Question, QuestionCluster
from sidecar.app import create_app
from pathlib import Path

def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    s = get_session()
    cl = QuestionCluster(name="季节", description="d", question_count=1)
    s.add(cl); s.flush()
    s.add(Question(normalized_text="几月去", raw_text="几月去", source_ref=1, cluster_id=cl.id))
    s.commit()
    return TestClient(create_app()), cl.id

def test_list_clusters(tmp_path, monkeypatch):
    client, cl_id = _setup(tmp_path, monkeypatch)
    r = client.get("/questions/clusters")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["name"] == "季节"

def test_list_questions_by_cluster(tmp_path, monkeypatch):
    client, cl_id = _setup(tmp_path, monkeypatch)
    r = client.get(f"/clusters/{cl_id}/questions")
    assert r.status_code == 200
    assert len(r.json()) >= 1

def test_rename_cluster(tmp_path, monkeypatch):
    client, cl_id = _setup(tmp_path, monkeypatch)
    r = client.put(f"/clusters/{cl_id}", json={"name": "季节·最佳时间"})
    assert r.status_code == 200
    s = get_session()
    assert s.query(QuestionCluster).get(cl_id).name == "季节·最佳时间"
