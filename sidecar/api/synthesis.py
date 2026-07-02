from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sidecar.db.session import get_session
from sidecar.db.models import Asset, ScrapeJob
from sidecar.jobs.queue import submit
from sidecar.jobs.synthesis import run_synthesis
import asyncio

router = APIRouter()

class ExtractIn(BaseModel):
    material_ids: list[int]
    types: list[str]

@router.post("/synthesis/extract")
def extract(body: ExtractIn):
    s = get_session()
    job = ScrapeJob(type="synthesis", status="queued", params={"material_ids": body.material_ids, "types": body.types})
    s.add(job); s.commit(); s.refresh(job)
    def _run():
        run_synthesis(body.material_ids, body.types, job_id=job.id)
    submit(asyncio.to_thread(_run))
    return {"job_id": job.id}

@router.get("/assets")
def list_assets(type: str | None = None, include_disliked: bool = False):
    s = get_session()
    q = s.query(Asset)
    if type:
        q = q.filter_by(type=type)
    if not include_disliked:
        q = q.filter_by(disliked=False)
    return [{"id": a.id, "type": a.type, "text": a.text,
             "derived_from": a.derived_from, "tags": a.tags, "disliked": a.disliked}
            for a in q.order_by(Asset.created_at.desc()).all()]

class AssetUpdateIn(BaseModel):
    text: str | None = None
    disliked: bool | None = None

@router.put("/assets/{aid}")
def update_asset(aid: int, body: AssetUpdateIn):
    s = get_session()
    a = s.query(Asset).get(aid)
    if not a:
        raise HTTPException(404)
    if body.text is not None:
        a.text = body.text
    if body.disliked is not None:
        a.disliked = body.disliked
    s.commit()
    return {"ok": True}

@router.delete("/assets/{aid}")
def delete_asset(aid: int):
    s = get_session()
    a = s.query(Asset).get(aid)
    if not a:
        raise HTTPException(404)
    s.delete(a); s.commit()
    return {"ok": True}
