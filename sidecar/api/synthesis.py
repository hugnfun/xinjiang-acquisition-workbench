from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sidecar.db.session import get_db
from sidecar.db.models import Asset, ScrapeJob
from sidecar.jobs.queue import submit
from sidecar.jobs.synthesis import run_synthesis

router = APIRouter()

class ExtractIn(BaseModel):
    material_ids: list[int]
    types: list[str]

@router.post("/synthesis/extract")
def extract(body: ExtractIn, s: Session = Depends(get_db)):
    job = ScrapeJob(type="synthesis", status="queued", params={"material_ids": body.material_ids, "types": body.types})
    s.add(job); s.commit(); s.refresh(job)
    submit(job.id, run_synthesis, body.material_ids, body.types, job.id)
    return {"job_id": job.id}

@router.get("/assets")
def list_assets(
    type: str | None = None, include_disliked: bool = False,
    status: str | None = None,
    s: Session = Depends(get_db),
):
    q = s.query(Asset)
    if type:
        q = q.filter_by(type=type)
    if not include_disliked:
        q = q.filter_by(disliked=False)
    if status:
        q = q.filter_by(status=status)
    return [{"id": a.id, "type": a.type, "text": a.text,
             "derived_from": a.derived_from, "tags": a.tags, "disliked": a.disliked,
             "status": a.status, "quality": a.quality, "reject_reason": a.reject_reason}
            for a in q.order_by(Asset.created_at.desc()).all()]

class AssetUpdateIn(BaseModel):
    text: str | None = None
    disliked: bool | None = None
    status: str | None = None
    quality: int | None = None
    reject_reason: str | None = None

@router.put("/assets/{aid}")
def update_asset(
    aid: int, body: AssetUpdateIn, s: Session = Depends(get_db)
):
    a = s.query(Asset).get(aid)
    if not a:
        raise HTTPException(404)
    if body.text is not None:
        a.text = body.text
    if body.disliked is not None:
        a.disliked = body.disliked
    if body.status is not None:
        a.status = body.status
    if body.quality is not None:
        a.quality = body.quality
    if body.reject_reason is not None:
        a.reject_reason = body.reject_reason
    s.commit()
    return {"ok": True}

@router.delete("/assets/{aid}")
def delete_asset(aid: int, s: Session = Depends(get_db)):
    a = s.query(Asset).get(aid)
    if not a:
        raise HTTPException(404)
    s.delete(a); s.commit()
    return {"ok": True}
