import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sidecar.db.session import get_session
from sidecar.db.models import ScrapeJob, JobLog
from sidecar.jobs.queue import submit
from sidecar.jobs.label import run_label_job, run_relabel_job
from sidecar.jobs.question_pool import run_question_pool_job, run_question_pool_incremental
from sidecar.jobs.scrape import run_scrape_job, run_scrape_note_job, run_scrape_user_job
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
        "progress": j.progress, "progress_total": j.progress_total,
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
        "progress": j.progress, "progress_total": j.progress_total,
        "logs": [{"level": l.level, "message": l.message,
                  "created_at": l.created_at.isoformat() if l.created_at else None}
                 for l in logs],
    }


# spec §5.5 失败重试
@router.post("/jobs/{jid}/retry")
def retry_job(jid: int):
    s = get_session()
    j = s.query(ScrapeJob).get(jid)
    if not j:
        raise HTTPException(404)
    if j.status not in ("failed", "cancelled"):
        raise HTTPException(400, f"job status is {j.status}, only failed/cancelled can retry")
    j.status = "queued"
    j.error = None
    j.progress = 0
    s.commit()
    _dispatch(s, j)
    return {"job_id": j.id}


def _dispatch(s, job: ScrapeJob):
    """根据 job.type 和 params 重新提交执行。"""
    jid = job.id
    p = job.params or {}
    t = job.type
    if t == "label_batch":
        submit(asyncio.to_thread(run_label_job, jid))
    elif t == "relabel":
        submit(asyncio.to_thread(run_relabel_job, jid, p.get("material_ids", [])))
    elif t == "question_pool":
        if p.get("mode") == "incremental":
            submit(asyncio.to_thread(run_question_pool_incremental, jid))
        else:
            submit(asyncio.to_thread(run_question_pool_job, jid))
    elif t == "report":
        submit(asyncio.to_thread(run_report_job, jid))
    elif t == "scrape":
        mode = p.get("mode", "keyword")
        if mode == "note":
            submit(asyncio.to_thread(run_scrape_note_job, jid, p.get("url", "")))
        elif mode == "user":
            submit(asyncio.to_thread(run_scrape_user_job, jid, p.get("url", ""), p.get("limit", 20)))
        else:
            submit(asyncio.to_thread(run_scrape_job, jid, p.get("keyword", ""), p.get("limit", 20)))


@router.post("/jobs/label")
def trigger_label():
    s = get_session()
    job = ScrapeJob(type="label_batch", status="queued", params={})
    s.add(job); s.commit(); s.refresh(job)
    submit(asyncio.to_thread(run_label_job, job.id))
    return {"job_id": job.id}


# spec §5.1 批量触发 AI 重打标
class RelabelIn(BaseModel):
    material_ids: list[int]


@router.post("/jobs/relabel")
def trigger_relabel(body: RelabelIn):
    s = get_session()
    job = ScrapeJob(type="relabel", status="queued",
                    params={"material_ids": body.material_ids})
    s.add(job); s.commit(); s.refresh(job)
    submit(asyncio.to_thread(run_relabel_job, job.id, body.material_ids))
    return {"job_id": job.id}


class QuestionPoolIn(BaseModel):
    mode: str = "full"  # full=全量冷启动 | incremental=只处理新评论


@router.post("/jobs/question-pool")
def trigger_question_pool(body: QuestionPoolIn | None = None):
    mode = (body.mode if body else "full") or "full"
    s = get_session()
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


# spec §5.5 抓取 tab：新关键词搜索 / 抓某条评论(笔记) / 抓某用户主页
class ScrapeIn(BaseModel):
    mode: str = "keyword"  # keyword | note | user
    keyword: str | None = None
    url: str | None = None
    limit: int = 20


@router.post("/jobs/scrape")
def trigger_scrape(body: ScrapeIn):
    s = get_session()
    mode = body.mode or "keyword"
    if mode == "note":
        if not body.url:
            raise HTTPException(400, "note mode requires url")
        params = {"mode": "note", "url": body.url}
        job = ScrapeJob(type="scrape", status="queued", params=params)
        s.add(job); s.commit(); s.refresh(job)
        submit(asyncio.to_thread(run_scrape_note_job, job.id, body.url))
    elif mode == "user":
        if not body.url:
            raise HTTPException(400, "user mode requires url")
        params = {"mode": "user", "url": body.url, "limit": body.limit}
        job = ScrapeJob(type="scrape", status="queued", params=params)
        s.add(job); s.commit(); s.refresh(job)
        submit(asyncio.to_thread(run_scrape_user_job, job.id, body.url, body.limit))
    else:
        if not body.keyword:
            raise HTTPException(400, "keyword mode requires keyword")
        params = {"mode": "keyword", "keyword": body.keyword, "limit": body.limit}
        job = ScrapeJob(type="scrape", status="queued", params=params)
        s.add(job); s.commit(); s.refresh(job)
        submit(asyncio.to_thread(run_scrape_job, job.id, body.keyword, body.limit))
    return {"job_id": job.id}
