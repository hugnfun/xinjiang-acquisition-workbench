import numpy as np
from pathlib import Path
import scripts.seed_taxonomy as seed
import scripts.import_from_folder as imp
from sidecar.jobs import question_pool as qp
from sidecar.db.session import get_session
from sidecar.db.models import Comment, Question, QuestionCluster, ScrapeJob


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")


def test_incremental_merges_similar_and_creates_new_dissimilar(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    s = get_session()
    # 现有簇 + 把 fixture 所有非回复评论都标为已处理（增量只该看新增的）
    existing = s.query(Comment).filter_by(is_reply=False).all()
    assert len(existing) >= 1
    cl = QuestionCluster(name="已有", description="", question_count=len(existing))
    s.add(cl); s.flush()
    v1 = np.array([1.0, 0.0], dtype=np.float32)
    for c in existing:
        s.add(Question(normalized_text="已有", raw_text="已有", source_ref=c.id,
                       source_type="comment", embedding=v1.tobytes(), cluster_id=cl.id))
    # 两条新评论：相似(应并入)、不相似(应新建簇)
    mid = existing[0].material_id
    c2 = Comment(material_id=mid, rank=10, author="a", text="相似新问题",
                 likes=0, time="t", is_reply=False, reply_to="")
    c3 = Comment(material_id=mid, rank=11, author="b", text="不相似新问题",
                 likes=0, time="t", is_reply=False, reply_to="")
    s.add_all([c2, c3]); s.commit()
    existing_cid = cl.id

    monkeypatch.setattr(qp.tc, "filter_questions",
                        lambda payload: [{"raw": p["raw"], "is_question": True} for p in payload])
    monkeypatch.setattr(qp.tc, "normalize_questions",
                        lambda qs: [{"raw": q["raw"], "normalized": q["raw"]} for q in qs])
    monkeypatch.setattr(qp.tc, "name_cluster", lambda samples: {"name": "新簇", "description": "d"})
    v_sim = np.array([0.99, 0.01], dtype=np.float32)   # cos(v1)≈0.9999 > 0.78 → 并入
    v_dis = np.array([0.0, 1.0], dtype=np.float32)     # cos(v1)=0 → 新建
    monkeypatch.setattr(qp.emb, "embed_batch",
                        lambda texts: np.array([v_sim, v_dis][:len(texts)], dtype=np.float32))

    job = ScrapeJob(type="question_pool", status="queued", params={"mode": "incremental"})
    s.add(job); s.commit()
    qp.run_question_pool_incremental(job.id)

    s2 = get_session()
    j = s2.query(ScrapeJob).get(job.id)
    assert j.status == "done"
    assert j.result_summary == {"new_questions": 2, "merged": 1, "new_clusters": 1}
    qs = s2.query(Question).filter(Question.source_ref.in_([c2.id, c3.id])).all()
    assert len(qs) == 2
    by_src = {q.source_ref: q.cluster_id for q in qs}
    assert by_src[c2.id] == existing_cid          # 相似 → 并入现有簇
    assert by_src[c3.id] != existing_cid          # 不相似 → 新建簇
    new_cl = s2.query(QuestionCluster).get(by_src[c3.id])
    assert new_cl.name == "新簇"                  # 新簇被命名


def test_incremental_no_new_comments_done_quickly(tmp_path, monkeypatch):
    """无新评论时快速完成，不调用 LLM。"""
    _setup(tmp_path, monkeypatch)
    s = get_session()
    # 把所有非回复评论都标为已处理
    existing = s.query(Comment).filter_by(is_reply=False).all()
    cl = QuestionCluster(name="x", description="", question_count=len(existing))
    s.add(cl); s.flush()
    v = np.array([1.0, 0.0], dtype=np.float32).tobytes()
    for c in existing:
        s.add(Question(normalized_text="x", raw_text="x", source_ref=c.id,
                       source_type="comment", embedding=v, cluster_id=cl.id))
    s.commit()
    called = {"filter": 0}
    monkeypatch.setattr(qp.tc, "filter_questions", lambda p: called.__setitem__("filter", called["filter"] + 1) or [])
    job = ScrapeJob(type="question_pool", status="queued", params={"mode": "incremental"})
    s.add(job); s.commit()
    qp.run_question_pool_incremental(job.id)
    s2 = get_session()
    j = s2.query(ScrapeJob).get(job.id)
    assert j.status == "done"
    assert j.result_summary == {"new_questions": 0, "merged": 0, "new_clusters": 0}
    assert called["filter"] == 0  # 无新评论不该调 filter


def test_non_question_comment_is_not_sent_again(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    calls = {"filter": 0}

    def reject_all(payload):
        calls["filter"] += 1
        return [{"raw": item["raw"], "is_question": False} for item in payload]

    monkeypatch.setattr(qp.tc, "filter_questions", reject_all)
    s = get_session()
    first = ScrapeJob(
        type="question_pool", status="queued", params={"mode": "incremental"}
    )
    s.add(first); s.commit()
    first_id = first.id
    s.close()
    qp.run_question_pool_incremental(first_id)

    s = get_session()
    second = ScrapeJob(
        type="question_pool", status="queued", params={"mode": "incremental"}
    )
    s.add(second); s.commit()
    second_id = second.id
    statuses = {
        c.question_status for c in s.query(Comment).filter_by(is_reply=False).all()
    }
    s.close()
    qp.run_question_pool_incremental(second_id)

    assert calls["filter"] == 1
    assert statuses == {"not_question"}


def test_failed_filter_batch_stays_pending_for_retry(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        qp.tc, "filter_questions",
        lambda payload: (_ for _ in ()).throw(RuntimeError("provider down")),
    )
    s = get_session()
    job = ScrapeJob(
        type="question_pool", status="queued", params={"mode": "incremental"}
    )
    s.add(job); s.commit()
    jid = job.id
    s.close()
    qp.run_question_pool_incremental(jid)

    s = get_session()
    assert s.get(ScrapeJob, jid).status == "failed"
    assert {
        c.question_status for c in s.query(Comment).filter_by(is_reply=False).all()
    } == {"pending"}
    s.close()
