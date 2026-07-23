from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sidecar.db.session import get_db
from sidecar.db.models import Question, QuestionCluster

router = APIRouter()


@router.get("/questions/clusters")
def list_clusters(s: Session = Depends(get_db)):
    # spec §5.3 左：cluster 树（可多级），返回 parent_id 供前端构建树
    return [{"id": c.id, "name": c.name, "description": c.description,
             "question_count": c.question_count, "parent_id": c.parent_id}
            for c in s.query(QuestionCluster).order_by(QuestionCluster.question_count.desc()).all()]


@router.get("/clusters/{cid}/questions")
def cluster_questions(cid: int, s: Session = Depends(get_db)):
    return [{"id": q.id, "normalized_text": q.normalized_text, "raw_text": q.raw_text,
             "source_ref": q.source_ref, "source_type": q.source_type}
            for q in s.query(Question).filter_by(cluster_id=cid).all()]


@router.get("/questions")
def list_questions(
    cluster_id: int | None = None, s: Session = Depends(get_db)
):
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
def rename_cluster(cid: int, body: RenameIn, s: Session = Depends(get_db)):
    c = s.query(QuestionCluster).get(cid)
    if not c:
        raise HTTPException(404)
    c.name = body.name
    if body.description is not None:
        c.description = body.description
    s.commit()
    return {"ok": True}


@router.delete("/clusters/{cid}")
def delete_cluster(cid: int, s: Session = Depends(get_db)):
    # 只允许删除空簇（question_count=0），避免误删有问题的簇。
    # 如果有子簇也一并拒绝——先处理子簇再删父簇。
    c = s.query(QuestionCluster).get(cid)
    if not c:
        raise HTTPException(404)
    remaining = s.query(Question).filter_by(cluster_id=cid).count()
    if remaining > 0:
        raise HTTPException(400, f"簇里还有 {remaining} 个问题，请先合并或移走再删除")
    children = s.query(QuestionCluster).filter_by(parent_id=cid).count()
    if children > 0:
        raise HTTPException(400, "簇下还有子簇，请先处理子簇再删除")
    s.delete(c)
    s.commit()
    return {"ok": True}


# spec §5.3 顶部：新建 cluster
class CreateClusterIn(BaseModel):
    name: str = ""
    description: str = ""
    parent_id: int | None = None


@router.post("/clusters")
def create_cluster(body: CreateClusterIn, s: Session = Depends(get_db)):
    cl = QuestionCluster(name=body.name, description=body.description,
                          question_count=0, parent_id=body.parent_id)
    s.add(cl)
    s.commit()
    s.refresh(cl)
    return {"id": cl.id, "name": cl.name, "description": cl.description,
            "parent_id": cl.parent_id, "question_count": 0}


# spec §5.3 顶部：合并 cluster
class MergeClustersIn(BaseModel):
    source_id: int
    target_id: int


@router.post("/clusters/merge")
def merge_clusters(body: MergeClustersIn, s: Session = Depends(get_db)):
    src = s.query(QuestionCluster).get(body.source_id)
    tgt = s.query(QuestionCluster).get(body.target_id)
    if not src or not tgt:
        raise HTTPException(404, "source or target cluster not found")
    if src.id == tgt.id:
        raise HTTPException(400, "cannot merge into itself")
    # 把所有问题从 source 搬到 target
    for q in s.query(Question).filter_by(cluster_id=src.id).all():
        q.cluster_id = tgt.id
    tgt.question_count += src.question_count
    src.question_count = 0
    s.commit()
    return {"ok": True, "merged_into": tgt.id}


# spec §5.3 顶部：拆分 cluster（把指定问题抽出建新簇）
class SplitClusterIn(BaseModel):
    question_ids: list[int]
    new_cluster_name: str = ""


@router.post("/clusters/{cid}/split")
def split_cluster(
    cid: int, body: SplitClusterIn, s: Session = Depends(get_db)
):
    parent = s.query(QuestionCluster).get(cid)
    if not parent:
        raise HTTPException(404)
    new_cl = QuestionCluster(name=body.new_cluster_name, description="",
                             question_count=0, parent_id=parent.parent_id)
    s.add(new_cl)
    s.flush()
    moved = 0
    for qid in body.question_ids:
        q = s.query(Question).get(qid)
        if q and q.cluster_id == cid:
            q.cluster_id = new_cl.id
            moved += 1
    new_cl.question_count = moved
    parent.question_count = s.query(Question).filter_by(cluster_id=cid).count()
    s.commit()
    s.refresh(new_cl)
    return {"ok": True, "new_cluster_id": new_cl.id, "moved": moved}


# spec §5.3 顶部：移动 cluster 到父节点下（多级树拖拽）
class MoveClusterIn(BaseModel):
    parent_id: int | None = None


@router.put("/clusters/{cid}/move")
def move_cluster(
    cid: int, body: MoveClusterIn, s: Session = Depends(get_db)
):
    cl = s.query(QuestionCluster).get(cid)
    if not cl:
        raise HTTPException(404)
    if body.parent_id == cid:
        raise HTTPException(400, "cannot be own parent")
    cl.parent_id = body.parent_id
    s.commit()
    return {"ok": True}


# spec §5.3 顶部：改写归一化单条问题
class RewriteQuestionIn(BaseModel):
    normalized_text: str


@router.put("/questions/{qid}")
def rewrite_question(
    qid: int, body: RewriteQuestionIn, s: Session = Depends(get_db)
):
    q = s.query(Question).get(qid)
    if not q:
        raise HTTPException(404)
    q.normalized_text = body.normalized_text.strip()
    s.commit()
    return {"ok": True}


# spec §5.3 顶部：把问题移到另一 cluster
class MoveQuestionIn(BaseModel):
    target_cluster_id: int


@router.put("/questions/{qid}/move")
def move_question(
    qid: int, body: MoveQuestionIn, s: Session = Depends(get_db)
):
    q = s.query(Question).get(qid)
    if not q:
        raise HTTPException(404)
    old_cid = q.cluster_id
    q.cluster_id = body.target_cluster_id
    # 更新计数
    if old_cid:
        old = s.query(QuestionCluster).get(old_cid)
        if old:
            old.question_count = s.query(Question).filter_by(cluster_id=old_cid).count()
    tgt = s.query(QuestionCluster).get(body.target_cluster_id)
    if tgt:
        tgt.question_count = s.query(Question).filter_by(cluster_id=body.target_cluster_id).count()
    s.commit()
    return {"ok": True}
