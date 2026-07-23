"""问题池周报 job：MiniMax 总结当前热点簇 + 样本 → 一份简短运营周报。

spec §8 v0.3「Flow C 增量聚类 + 周报」的周报侧。输出 free-text（不走 JSON 解析），
存入 ScrapeJob.result_summary.report，前端任务详情可见。
"""
from datetime import datetime
from sidecar.db.session import session_scope
from sidecar.db.models import ScrapeJob, JobLog, QuestionCluster, Question
from sidecar.llm import task_client as tc
from sidecar.jobs.queue import cancellation_checkpoint


def _log(job_id, msg, level="info"):
    with session_scope() as s:
        s.add(JobLog(job_id=job_id, level=level, message=msg))


def _set_job(job_id, **fields):
    with session_scope() as s:
        job = s.query(ScrapeJob).get(job_id)
        for k, v in fields.items():
            setattr(job, k, v)


def run_report_job(job_id: int):
    _set_job(job_id, status="running", started_at=datetime.utcnow())
    _log(job_id, "生成问题池周报")
    try:
        if cancellation_checkpoint(job_id):
            return
        with session_scope() as s:
            clusters = (s.query(QuestionCluster)
                       .order_by(QuestionCluster.question_count.desc()).limit(15).all())
            lines = []
            for cl in clusters:
                samples = [q.raw_text for q in
                           s.query(Question).filter_by(cluster_id=cl.id).limit(3).all()]
                lines.append(f"- {cl.name or '(未命名)'}（{cl.question_count}问）：{' / '.join(samples)}")
        system = ("你是内容运营助手。基于问题池的热点簇+问题样本，输出一份简短周报："
                 "本周用户最关心的话题 top3、以及 2-3 个值得做内容的方向。中文，300 字内。")
        user = "问题池热点簇：\n" + "\n".join(lines) if lines else "问题池为空"
        report = tc.chat_json(system, user)  # free-text，无需 JSON 解析
        if cancellation_checkpoint(job_id):
            return
        _set_job(job_id, status="done",
                 result_summary={"report": (report or "").strip()[:2000],
                                 "clusters_summarized": len(lines)},
                 finished_at=datetime.utcnow())
        _log(job_id, f"周报生成完成（{len(report or '')} 字）")
    except Exception as e:
        _set_job(job_id, status="failed", error=str(e), finished_at=datetime.utcnow())
        _log(job_id, f"失败: {e}", "error")
