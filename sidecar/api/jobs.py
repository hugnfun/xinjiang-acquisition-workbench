import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sidecar.db.session import get_session
from sidecar.db.models import ScrapeJob, JobLog
from sidecar.jobs.queue import submit
from sidecar.jobs.label import run_label_job
from sidecar.jobs.question_pool import run_question_pool_job, run_question_pool_incremental
from sidecar.jobs.scrape import run_scrape_job
from sidecar.jobs.report import run_report_job

router = APIRouter()

@router.get("/jobs")
def list_jobs(limit: int = 50):
    s = get_session()
    jobs = s.query(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(limit).all()
    return [{
        "id": j.id, "type": j.type, "status": j.status,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        "error": j.error,
    } for j in jobs]

@router.get("/jobs/{jid}")
def get_job(jid: int):
    s = get_session()
    j = s.query(ScrapeJob).get(jid)
    if not j:
        raise HTTPException(404)
    logs = s.query(JobLog).filter_by(job_id=jid).order_by(JobLog.created_at).all()
    return {
        "id": j.id, "type": j.type, "status": j.status,
        "params": j.params, "result_summary": j.result_summary, "error": j.error,
        "logs": [{"level": l.level, "message": l.message,
                  "created_at": l.created_at.isoformat() if l.created_at else None}
                 for l in logs],
    }

@router.post("/jobs/label")
def trigger_label():
    s = get_session()
    from sidecar.db.models import ScrapeJob
    job = ScrapeJob(type="label_batch", status="queued", params={})
    s.add(job); s.commit(); s.refresh(job)
    submit(asyncio.to_thread(run_label_job, job.id))
    return {"job_id": job.id}

class QuestionPoolIn(BaseModel):
    mode: str = "full"  # full=全量冷启动 | incremental=只处理新评论


@router.post("/jobs/question-pool")
def trigger_question_pool(body: QuestionPoolIn | None = None):
    mode = (body.mode if body else "full") or "full"
    s = get_session()
    from sidecar.db.models import ScrapeJob
    job = ScrapeJob(type="question_pool", status="queued", params={"mode": mode})
    s.add(job); s.commit(); s.refresh(job)
    if mode == "incremental":
        submit(asyncio.to_thread(run_question_pool_incremental, job.id))
    else:
        submit(asyncio.to_thread(run_question_pool_job, job.id))
    return {"job_id": job.id}


@router.post("/jobs/report")
def trigger_report():
    s = get_session()
    job = ScrapeJob(type="report", status="queued", params={})
    s.add(job); s.commit(); s.refresh(job)
    submit(asyncio.to_thread(run_report_job, job.id))
    return {"job_id": job.id}


class ScrapeIn(BaseModel):
    keyword: str
    limit: int = 20


@router.post("/jobs/scrape")
def trigger_scrape(body: ScrapeIn):
    s = get_session()
    job = ScrapeJob(type="scrape", status="queued",
                    params={"keyword": body.keyword, "limit": body.limit})
    s.add(job); s.commit(); s.refresh(job)
    submit(asyncio.to_thread(run_scrape_job, job.id, body.keyword, body.limit))
    return {"job_id": job.id}
