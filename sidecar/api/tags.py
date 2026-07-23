from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sidecar.db.session import get_session
from sidecar.db.models import TagDimension, TagValue, MaterialTag, TagSuggestion

router = APIRouter()


@router.get("/tags")
def list_tags():
    # spec §5.2 右侧：标签值列表（带命中素材数 + alias 数）
    s = get_session()
    out = []
    for d in s.query(TagDimension).all():
        values = []
        for v in d.values:
            hit_count = s.query(MaterialTag).filter_by(tag_value_id=v.id).count()
            values.append({
                "id": v.id, "value": v.value,
                "alias": v.alias, "status": v.status,
                "hit_count": hit_count,
            })
        out.append({
            "id": d.id, "name": d.name, "description": d.description,
            "values": values,
        })
    return out


@router.get("/tags/suggestions")
def list_suggestions():
    s = get_session()
    return [{
        "id": sg.id, "dimension_name": sg.dimension_name,
        "proposed_value": sg.proposed_value, "status": sg.status,
        "sample_context": sg.sample_context, "material_id": sg.material_id,
    } for sg in s.query(TagSuggestion).filter_by(status="pending").all()]


class SuggestionActionIn(BaseModel):
    action: str           # accept | reject | merge
    merge_into_value_id: int | None = None
    rename: str | None = None  # spec §6.2 改名后接受


@router.post("/tags/suggestions/{sid}")
def act_suggestion(sid: int, body: SuggestionActionIn):
    s = get_session()
    sg = s.query(TagSuggestion).get(sid)
    if not sg:
        raise HTTPException(404)
    if body.action == "accept":
        value = (body.rename or sg.proposed_value).strip()
        d = s.query(TagDimension).filter_by(name=sg.dimension_name).first()
        if d:
            s.add(TagValue(dimension_id=d.id, value=value, alias=[]))
        sg.status = "accepted"
    elif body.action == "merge" and body.merge_into_value_id:
        tv = s.query(TagValue).get(body.merge_into_value_id)
        if tv:
            tv.alias = [*tv.alias, sg.proposed_value]
        sg.status = "merged"
    elif body.action == "reject":
        sg.status = "rejected"
    s.commit()
    return {"ok": True}


# spec §5.2 操作：合并同义标签
class MergeTagsIn(BaseModel):
    source_id: int
    target_id: int


@router.post("/tags/merge")
def merge_tags(body: MergeTagsIn):
    s = get_session()
    src = s.query(TagValue).get(body.source_id)
    tgt = s.query(TagValue).get(body.target_id)
    if not src or not tgt:
        raise HTTPException(404, "source or target tag value not found")
    if src.id == tgt.id:
        raise HTTPException(400, "cannot merge into itself")
    # 把所有 material_tag 从 source 搬到 target，去重
    moved = 0
    for mt in s.query(MaterialTag).filter_by(tag_value_id=src.id).all():
        dup = s.query(MaterialTag).filter_by(
            material_id=mt.material_id, tag_value_id=tgt.id).first()
        if dup:
            s.delete(mt)
        else:
            mt.tag_value_id = tgt.id
            moved += 1
    # 旧名进 alias
    tgt.alias = [*tgt.alias, src.value]
    # 软弃用 source
    src.status = "deprecated"
    s.commit()
    return {"ok": True, "moved": moved}


# spec §5.2 操作：改名 / 加 alias / 弃用
class TagValueUpdateIn(BaseModel):
    value: str | None = None
    add_alias: str | None = None
    status: str | None = None  # active | deprecated


@router.put("/tag-values/{vid}")
def update_tag_value(vid: int, body: TagValueUpdateIn):
    s = get_session()
    tv = s.query(TagValue).get(vid)
    if not tv:
        raise HTTPException(404)
    if body.value is not None:
        tv.value = body.value
    if body.add_alias:
        if body.add_alias not in tv.alias:
            tv.alias = [*tv.alias, body.add_alias]
    if body.status:
        tv.status = body.status
    s.commit()
    return {"ok": True}


# spec §5.2 左侧：新建维度
class CreateDimensionIn(BaseModel):
    name: str
    description: str = ""


@router.post("/tag-dimensions")
def create_dimension(body: CreateDimensionIn):
    s = get_session()
    exists = s.query(TagDimension).filter_by(name=body.name.strip()).first()
    if exists:
        raise HTTPException(409, "dimension already exists")
    d = TagDimension(name=body.name.strip(), description=body.description)
    s.add(d)
    s.commit()
    s.refresh(d)
    return {"id": d.id, "name": d.name, "description": d.description}


# spec §5.2 右侧：新建标签值
class CreateTagValueIn(BaseModel):
    value: str


@router.post("/tag-dimensions/{did}/values")
def create_tag_value(did: int, body: CreateTagValueIn):
    s = get_session()
    d = s.query(TagDimension).get(did)
    if not d:
        raise HTTPException(404)
    exists = s.query(TagValue).filter_by(dimension_id=did, value=body.value.strip()).first()
    if exists:
        raise HTTPException(409, "tag value already exists")
    tv = TagValue(dimension_id=did, value=body.value.strip(), alias=[])
    s.add(tv)
    s.commit()
    s.refresh(tv)
    return {"id": tv.id, "value": tv.value, "alias": tv.alias, "status": tv.status}
