from pathlib import Path
import scripts.seed_taxonomy as seed
import scripts.import_from_folder as imp
from sidecar.jobs import report as rp
from sidecar.db.session import get_session
from sidecar.db.models import QuestionCluster, Question, ScrapeJob
import numpy as np


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")


def _seed_clusters():
    s = get_session()
    cl = QuestionCluster(name="费用与时间", description="d", question_count=2)
    s.add(cl); s.flush()
    v = np.array([1.0, 0.0], dtype=np.float32).tobytes()
    s.add(Question(normalized_text="多少钱", raw_text="一共多少钱", source_ref=1,
                   source_type="comment", embedding=v, cluster_id=cl.id))
    s.add(Question(normalized_text="几月去", raw_text="6月合适吗", source_ref=2,
                   source_type="comment", embedding=v, cluster_id=cl.id))
    s.commit()
    return cl.id


def test_run_report_job_stores_summary(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _seed_clusters()
    monkeypatch.setattr(rp.tc, "chat_json", lambda sys, usr: "本周热点：费用与出行时间最受关注。建议做预算攻略。")
    s = get_session()
    job = ScrapeJob(type="report", status="queued", params={})
    s.add(job); s.commit()
    rp.run_report_job(job.id)
    s2 = get_session()
    j = s2.query(ScrapeJob).get(job.id)
    assert j.status == "done"
    assert "本周热点" in j.result_summary["report"]
    assert j.result_summary["clusters_summarized"] == 1


def test_run_report_job_handles_empty_pool(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)  # 无簇
    monkeypatch.setattr(rp.tc, "chat_json", lambda sys, usr: "问题池为空，无内容。")
    s = get_session()
    job = ScrapeJob(type="report", status="queued", params={})
    s.add(job); s.commit()
    rp.run_report_job(job.id)
    s2 = get_session()
    j = s2.query(ScrapeJob).get(job.id)
    assert j.status == "done"
    assert j.result_summary["clusters_summarized"] == 0
