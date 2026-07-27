"""把 task_client 的用量聚合实时写入后台任务。"""
from sidecar.db.models import ScrapeJob
from sidecar.db.session import session_scope
from sidecar.llm.task_client import UsageAccumulator


def job_usage_accumulator(job_id: int | None) -> UsageAccumulator:
    def persist(snapshot: dict) -> None:
        if job_id is None:
            return
        with session_scope() as s:
            job = s.get(ScrapeJob, job_id)
            if job:
                job.token_usage = snapshot

    return UsageAccumulator(on_change=persist)
