from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sidecar.db.session import get_session
from sidecar.db.models import Question, QuestionCluster

router = APIRouter()

@router.get("/questions/clusters")
def list_clusters():
    s = get_session()
    return [{"id": c.id, "name": c.name, "description": c.description,
             "question_count": c.question_count}
            for c in s.query(QuestionCluster).order_by(QuestionCluster.question_count.desc()).all()]

@router.get("/clusters/{cid}/questions")
def cluster_questions(cid: int):
    s = get_session()
    return [{"id": q.id, "normalized_text": q.normalized_text, "raw_text": q.raw_text,
             "source_ref": q.source_ref, "source_type": q.source_type}
            for q in s.query(Question).filter_by(cluster_id=cid).all()]

@router.get("/questions")
def list_questions(cluster_id: int | None = None):
    s = get_session()
    q = s.query(Question)
    if cluster_id:
        q = q.filter_by(cluster_id=cluster_id)
    return [{"id": x.id, "normalized_text": x.normalized_text, "raw_text": x.raw_text,
             "cluster_id": x.cluster_id, "source_ref": x.source_ref}
            for x in q.all()]

class RenameIn(BaseModel):
    name: str
    description: str | None = None

@router.put("/clusters/{cid}")
def rename_cluster(cid: int, body: RenameIn):
    s = get_session()
    c = s.query(QuestionCluster).get(cid)
    if not c:
        raise HTTPException(404)
    c.name = body.name
    if body.description is not None:
        c.description = body.description
    s.commit()
    return {"ok": True}
