from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sidecar.db.session import get_db
from sidecar.db.models import Asset, ScrapeJob, QuestionCluster
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
             "status": a.status, "quality": a.quality, "reject_reason": a.reject_reason,
             "cluster_id": a.cluster_id, "target_audience": a.target_audience,
             "source_job_id": a.source_job_id, "model_name": a.model_name,
             "prompt_version": a.prompt_version, "token_usage": a.token_usage}
            for a in q.order_by(Asset.created_at.desc()).all()]

class AssetUpdateIn(BaseModel):
    text: str | None = None
    disliked: bool | None = None
    status: str | None = None
    quality: int | None = None
    reject_reason: str | None = None
    cluster_id: int | None = None
    target_audience: str | None = None

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
    if body.cluster_id is not None:
        a.cluster_id = body.cluster_id if body.cluster_id > 0 else None
    if body.target_audience is not None:
        a.target_audience = body.target_audience
    s.commit()
    return {"ok": True}

@router.delete("/assets/{aid}")
def delete_asset(aid: int, s: Session = Depends(get_db)):
    a = s.query(Asset).get(aid)
    if not a:
        raise HTTPException(404)
    s.delete(a); s.commit()
    return {"ok": True}


@router.get("/coverage")
def coverage(s: Session = Depends(get_db)):
    """问题簇 -> 合成物覆盖分析。

    返回每个问题簇的关联 asset 数量，以及未覆盖簇列表。
    """
    clusters = s.query(QuestionCluster).order_by(
        QuestionCluster.question_count.desc()
    ).all()
    result = []
    for c in clusters:
        assets = s.query(Asset).filter_by(cluster_id=c.id, disliked=False).all()
        result.append({
            "cluster_id": c.id,
            "cluster_name": c.name or f"簇 #{c.id}",
            "question_count": c.question_count,
            "asset_count": len(assets),
            "covered": len(assets) > 0,
            "asset_types": list({a.type for a in assets}),
            "assets": [{"id": a.id, "type": a.type, "text": a.text[:80],
                        "status": a.status} for a in assets[:5]],
        })
    covered = sum(1 for r in result if r["covered"])
    uncovered = [r for r in result if not r["covered"]]
    return {
        "total_clusters": len(result),
        "covered_clusters": covered,
        "uncovered_clusters": len(uncovered),
        "top_uncovered": sorted(uncovered, key=lambda x: x["question_count"], reverse=True)[:10],
        "clusters": result,
    }
