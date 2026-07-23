"""Tests for spec §5.1-§5.5 new endpoints: search/filter/sort, batch tag,
tag suggest_new, tags merge/rename/deprecate/create, questions multi-level
tree/merge/split/new/rewrite, jobs scrape-modes/retry/relabel/progress."""
from fastapi.testclient import TestClient
import scripts.import_from_folder as imp
import scripts.seed_taxonomy as seed
from sidecar.app import create_app
from sidecar.db.session import get_session
from sidecar.db.models import (Material, MaterialTag, TagDimension, TagValue,
                               TagSuggestion, QuestionCluster, Question, ScrapeJob)
from pathlib import Path


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    # Prevent background jobs from actually running (they'd call LLM/opencli APIs)
    monkeypatch.setattr("sidecar.api.jobs.submit", lambda *args, **kwargs: None)
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")
    return TestClient(create_app())


# ── §5.1 materials: search / filter / sort / batch ──

def test_search_materials(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.get("/materials?search=测试")
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    r2 = client.get("/materials?search=不存在的关键词xyz")
    assert r2.json()["total"] == 0


def test_sort_by_collects(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.get("/materials?order=collects")
    assert r.status_code == 200
    r2 = client.get("/materials?order=latest")
    assert r2.status_code == 200


def test_filter_by_tag(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    mid = client.get("/materials").json()["items"][0]["id"]
    tv = s.query(TagValue).first()
    tv_id = tv.id
    s.add(MaterialTag(material_id=mid, tag_value_id=tv.id, source="human",
                      confidence=None, confirmed_by_human=True))
    s.commit()
    s.close()
    r = client.get(f"/materials?tag_value_id={tv_id}")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_batch_tag(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    mid = client.get("/materials").json()["items"][0]["id"]
    tv = s.query(TagValue).first()
    tv_id = tv.id
    s.close()
    r = client.post("/materials/batch/tags", json={"material_ids": [mid], "tag_value_id": tv_id})
    assert r.status_code == 200
    assert r.json()["added"] == 1
    # duplicate should not add again
    r2 = client.post("/materials/batch/tags", json={"material_ids": [mid], "tag_value_id": tv_id})
    assert r2.json()["added"] == 0


def test_suggest_new_tag(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    mid = client.get("/materials").json()["items"][0]["id"]
    tv = s.query(TagValue).first()
    tv_id = tv.id
    s.close()
    r = client.post(f"/materials/{mid}/tags", json={
        "tag_value_id": tv_id, "action": "suggest_new",
        "new_dimension": "content_type", "new_value": "自定义标签",
    })
    assert r.status_code == 200
    s = get_session()
    sg = s.query(TagSuggestion).filter_by(proposed_value="自定义标签", status="pending").first()
    assert sg is not None
    s.close()


# ── §5.2 tags: hit_count / merge / rename / alias / deprecate / create ──

def test_tags_hit_count(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.get("/tags")
    assert r.status_code == 200
    dims = r.json()
    assert all("hit_count" in v for d in dims for v in d["values"])


def test_merge_tags(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    d = s.query(TagDimension).filter_by(name="content_type").first()
    src = d.values[0]
    tgt = d.values[1]
    src_value = src.value
    mid = client.get("/materials").json()["items"][0]["id"]
    s.add(MaterialTag(material_id=mid, tag_value_id=src.id, source="ai", confirmed_by_human=False))
    s.commit()
    src_id, tgt_id = src.id, tgt.id
    s.close()
    r = client.post("/tags/merge", json={"source_id": src_id, "target_id": tgt_id})
    assert r.status_code == 200
    s = get_session()
    assert s.query(MaterialTag).filter_by(material_id=mid, tag_value_id=tgt_id).first() is not None
    assert s.query(TagValue).get(src_id).status == "deprecated"
    assert src_value in s.query(TagValue).get(tgt_id).alias
    s.close()


def test_rename_tag_value(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    tv = s.query(TagValue).first()
    vid = tv.id
    s.close()
    r = client.put(f"/tag-values/{vid}", json={"value": "新名称"})
    assert r.status_code == 200
    s = get_session()
    assert s.query(TagValue).get(vid).value == "新名称"
    s.close()


def test_add_alias(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    tv = s.query(TagValue).first()
    vid = tv.id
    s.close()
    r = client.put(f"/tag-values/{vid}", json={"add_alias": "同义词A"})
    assert r.status_code == 200
    s = get_session()
    assert "同义词A" in s.query(TagValue).get(vid).alias
    s.close()


def test_deprecate_tag_value(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    tv = s.query(TagValue).first()
    vid = tv.id
    s.close()
    r = client.put(f"/tag-values/{vid}", json={"status": "deprecated"})
    assert r.status_code == 200
    s = get_session()
    assert s.query(TagValue).get(vid).status == "deprecated"
    s.close()


def test_create_dimension(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.post("/tag-dimensions", json={"name": "test_dim", "description": "test"})
    assert r.status_code == 200
    assert r.json()["name"] == "test_dim"
    # duplicate should 409
    r2 = client.post("/tag-dimensions", json={"name": "test_dim", "description": ""})
    assert r2.status_code == 409


def test_create_tag_value(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    d = s.query(TagDimension).first()
    did = d.id
    s.close()
    r = client.post(f"/tag-dimensions/{did}/values", json={"value": "新标签值"})
    assert r.status_code == 200
    assert r.json()["value"] == "新标签值"
    # duplicate should 409
    r2 = client.post(f"/tag-dimensions/{did}/values", json={"value": "新标签值"})
    assert r2.status_code == 409


# ── §5.3 questions: multi-level tree / merge / split / new / rewrite ──

def _seed_questions():
    s = get_session()
    parent = QuestionCluster(name="父簇", description="", question_count=1, parent_id=None)
    s.add(parent); s.flush()
    child = QuestionCluster(name="子簇", description="", question_count=1, parent_id=parent.id)
    s.add(child); s.flush()
    s.add(Question(normalized_text="几月去", raw_text="几月去新疆好", source_ref=1, cluster_id=parent.id))
    s.add(Question(normalized_text="多少钱", raw_text="去新疆要多少钱", source_ref=2, cluster_id=child.id))
    s.commit()
    p_id, c_id = parent.id, child.id
    s.close()
    return p_id, c_id


def test_clusters_return_parent_id(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    p_id, c_id = _seed_questions()
    r = client.get("/questions/clusters")
    data = {c["id"]: c for c in r.json()}
    assert data[p_id]["parent_id"] is None
    assert data[c_id]["parent_id"] == p_id


def test_create_cluster_with_parent(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    p_id, _ = _seed_questions()
    r = client.post("/clusters", json={"name": "新子簇", "description": "", "parent_id": p_id})
    assert r.status_code == 200
    assert r.json()["parent_id"] == p_id


def test_merge_clusters(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    p_id, c_id = _seed_questions()
    r = client.post("/clusters/merge", json={"source_id": c_id, "target_id": p_id})
    assert r.status_code == 200
    s = get_session()
    assert s.query(QuestionCluster).get(p_id).question_count == 2
    assert s.query(QuestionCluster).get(c_id).question_count == 0
    s.close()


def test_split_cluster(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    p_id, _ = _seed_questions()
    s = get_session()
    qid = s.query(Question).filter_by(cluster_id=p_id).first().id
    s.close()
    r = client.post(f"/clusters/{p_id}/split", json={"question_ids": [qid], "new_cluster_name": "拆分簇"})
    assert r.status_code == 200
    assert r.json()["moved"] == 1
    s = get_session()
    new_id = r.json()["new_cluster_id"]
    assert s.query(Question).get(qid).cluster_id == new_id
    s.close()


def test_rewrite_question(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    p_id, _ = _seed_questions()
    s = get_session()
    qid = s.query(Question).filter_by(cluster_id=p_id).first().id
    s.close()
    r = client.put(f"/questions/{qid}", json={"normalized_text": "什么时候去最好"})
    assert r.status_code == 200
    s = get_session()
    assert s.query(Question).get(qid).normalized_text == "什么时候去最好"
    s.close()


def test_move_question(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    p_id, c_id = _seed_questions()
    s = get_session()
    qid = s.query(Question).filter_by(cluster_id=p_id).first().id
    s.close()
    r = client.put(f"/questions/{qid}/move", json={"target_cluster_id": c_id})
    assert r.status_code == 200
    s = get_session()
    assert s.query(Question).get(qid).cluster_id == c_id
    s.close()


def test_delete_empty_cluster(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    cl = QuestionCluster(name="待删", description="", question_count=0, parent_id=None)
    s.add(cl); s.commit(); s.refresh(cl)
    cid = cl.id
    s.close()
    r = client.delete(f"/clusters/{cid}")
    assert r.status_code == 200
    s = get_session()
    assert s.query(QuestionCluster).get(cid) is None
    s.close()


def test_delete_cluster_with_questions_400(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    p_id, _ = _seed_questions()
    r = client.delete(f"/clusters/{p_id}")
    assert r.status_code == 400


# ── §5.5 jobs: scrape modes / retry / relabel / progress ──

def test_scrape_keyword_mode(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.post("/jobs/scrape", json={"mode": "keyword", "keyword": "测试", "limit": 5})
    assert r.status_code == 200
    assert "job_id" in r.json()


def test_scrape_note_mode_requires_url(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.post("/jobs/scrape", json={"mode": "note"})
    assert r.status_code == 400


def test_scrape_user_mode(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.post("/jobs/scrape", json={"mode": "user", "url": "https://example.com/user/123", "limit": 5})
    assert r.status_code == 200
    assert "job_id" in r.json()


def test_relabel_job(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    mid = client.get("/materials").json()["items"][0]["id"]
    r = client.post("/jobs/relabel", json={"material_ids": [mid]})
    assert r.status_code == 200
    assert "job_id" in r.json()


def test_retry_failed_job(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    job = ScrapeJob(type="scrape", status="failed", params={"mode": "keyword", "keyword": "x", "limit": 1},
                    error="test error")
    s.add(job); s.commit(); s.refresh(job)
    jid = job.id
    s.close()
    r = client.post(f"/jobs/{jid}/retry")
    assert r.status_code == 200
    s = get_session()
    assert s.query(ScrapeJob).get(jid).status == "queued"
    s.close()


def test_retry_non_failed_400(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    job = ScrapeJob(type="scrape", status="done", params={})
    s.add(job); s.commit(); s.refresh(job)
    jid = job.id
    s.close()
    r = client.post(f"/jobs/{jid}/retry")
    assert r.status_code == 400


def test_cancel_queued_job(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    job = ScrapeJob(type="report", status="queued", params={})
    s.add(job); s.commit(); s.refresh(job)
    jid = job.id
    s.close()
    r = client.post(f"/jobs/{jid}/cancel")
    assert r.status_code == 200
    s = get_session()
    saved = s.get(ScrapeJob, jid)
    assert saved.status == "cancelled"
    assert saved.finished_at is not None
    s.close()


def test_retry_synthesis_dispatches_again(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        "sidecar.api.jobs.submit",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    s = get_session()
    job = ScrapeJob(
        type="synthesis", status="failed",
        params={"material_ids": [1], "types": ["title"]},
        error="provider error",
    )
    s.add(job); s.commit(); s.refresh(job)
    jid = job.id
    s.close()
    r = client.post(f"/jobs/{jid}/retry")
    assert r.status_code == 200
    assert calls and calls[0][0][0] == jid
    assert calls[0][0][2:] == ([1], ["title"], jid)


def test_jobs_list_has_progress(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.get("/jobs")
    assert r.status_code == 200
    for j in r.json():
        assert "progress" in j
        assert "progress_total" in j


def test_job_detail_has_progress(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    job = ScrapeJob(type="scrape", status="done", params={}, progress=5, progress_total=10)
    s.add(job); s.commit(); s.refresh(job)
    jid = job.id
    s.close()
    r = client.get(f"/jobs/{jid}")
    assert r.status_code == 200
    assert r.json()["progress"] == 5
    assert r.json()["progress_total"] == 10


def test_full_question_pool_rejected_when_questions_exist(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    s = get_session()
    s.add(Question(
        normalized_text="已有问题", raw_text="已有问题",
        source_ref=999, source_type="comment",
    ))
    s.commit()
    s.close()
    r = client.post("/jobs/question-pool", json={"mode": "full"})
    assert r.status_code == 409
