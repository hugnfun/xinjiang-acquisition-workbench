import scripts.seed_taxonomy as seed
import scripts.import_from_folder as imp
from pathlib import Path
from sidecar.jobs import question_pool as qp

def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")

def test_run_question_pool_job(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    # mock 5 阶段的 LLM 调用
    monkeypatch.setattr(qp.tc, "filter_questions", lambda comments: [
        {"raw": c["raw"], "is_question": True} for c in comments
    ])
    monkeypatch.setattr(qp.tc, "normalize_questions", lambda qs: [
        {"raw": q["raw"], "normalized": "最佳时间"} for q in qs
    ])
    monkeypatch.setattr(qp.tc, "name_cluster", lambda samples: {"name": "季节·最佳时间", "description": "d"})
    # mock embedding（造固定向量，前2个相似）
    import numpy as np
    vecs = [np.array([1.0,0.0],dtype=np.float32), np.array([0.99,0.01],dtype=np.float32),
            np.array([0.0,1.0],dtype=np.float32), np.array([0.0,0.99],dtype=np.float32)]
    monkeypatch.setattr(qp.emb, "embed_batch", lambda texts: np.array(vecs[:len(texts)], dtype=np.float32))

    from sidecar.db.session import get_session
    from sidecar.db.models import ScrapeJob, Question, QuestionCluster
    s = get_session()
    job = ScrapeJob(type="question_pool", status="queued", params={})
    s.add(job); s.commit()
    qp.run_question_pool_job(job.id)

    s2 = get_session()
    job = s2.query(ScrapeJob).get(job.id)
    assert job.status == "done"
    # 过滤后 is_question 的进 question 表
    qs = s2.query(Question).all()
    assert len(qs) == 2
    # 聚类后有 cluster：2 个相似问题合并成 1 簇（真正的 Stage-4 断言）
    clusters = s2.query(QuestionCluster).all()
    assert len(clusters) == 1
    assert job.result_summary == {"questions": 2, "clusters": 1}
    # 每个 question 有 cluster_id
    assert all(q.cluster_id is not None for q in qs)
    # 簇有 name
    assert any(c.name for c in clusters)
