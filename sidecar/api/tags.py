from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sidecar.db.session import get_session
from sidecar.db.models import TagDimension, TagValue, MaterialTag, TagSuggestion

router = APIRouter()

@router.get("/tags")
def list_tags():
    s = get_session()
    out = []
    for d in s.query(TagDimension).all():
        out.append({
            "id": d.id, "name": d.name, "description": d.description,
            "values": [{"id": v.id, "value": v.value, "alias": v.alias, "status": v.status}
                       for v in d.values if v.status == "active"],
        })
    return out

class ConfirmTagIn(BaseModel):
    tag_value_id: int
    action: str  # 'confirm' | 'reject'

@router.post("/materials/{mid}/tags")
def manage_material_tag(mid: int, body: ConfirmTagIn):
    s = get_session()
    mt = s.query(MaterialTag).filter_by(material_id=mid, tag_value_id=body.tag_value_id).first()
    if body.action == "confirm":
        if mt:
            mt.confirmed_by_human = True
            mt.confirmed_at = datetime.utcnow()
        s.commit()
        return {"ok": True}
    elif body.action == "reject":
        if mt:
            s.delete(mt)
        s.commit()
        return {"ok": True}
    raise HTTPException(400, "unknown action")

@router.get("/tags/suggestions")
def list_suggestions():
    s = get_session()
    return [{
        "id": sg.id, "dimension_name": sg.dimension_name,
        "proposed_value": sg.proposed_value, "status": sg.status,
        "sample_context": sg.sample_context, "material_id": sg.material_id,
    } for sg in s.query(TagSuggestion).filter_by(status="pending").all()]

class SuggestionActionIn(BaseModel):
    action: str           # 'accept' | 'reject' | 'merge'
    merge_into_value_id: int | None = None

@router.post("/tags/suggestions/{sid}")
def act_suggestion(sid: int, body: SuggestionActionIn):
    s = get_session()
    sg = s.query(TagSuggestion).get(sid)
    if not sg:
        raise HTTPException(404)
    if body.action == "accept":
        d = s.query(TagDimension).filter_by(name=sg.dimension_name).first()
        if d:
            s.add(TagValue(dimension_id=d.id, value=sg.proposed_value, alias=[]))
        sg.status = "accepted"
    elif body.action == "merge" and body.merge_into_value_id:
        tv = s.query(TagValue).get(body.merge_into_value_id)
        if tv:
            tv.alias.append(sg.proposed_value)
        sg.status = "merged"
    elif body.action == "reject":
        sg.status = "rejected"
    s.commit()
    return {"ok": True}
