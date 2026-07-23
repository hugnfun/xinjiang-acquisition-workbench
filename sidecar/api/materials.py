from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sidecar.db.session import get_db
from sidecar.db.models import Material, MaterialTag, TagValue, TagDimension, TagSuggestion
from sidecar import config

router = APIRouter()


@router.get("/materials")
def list_materials(
    limit: int = 50, offset: int = 0, order: str = "likes",
    search: str | None = None, tag_value_id: int | None = None,
    s: Session = Depends(get_db),
):
    # spec §5.1 顶栏：搜索框 · 标签多维筛选器 · 排序（点赞/收藏/最新）
    q = s.query(Material)
    if search:
        kw = f"%{search.strip()}%"
        q = q.filter(
            (Material.title.like(kw)) | (Material.content.like(kw)) | (Material.author.like(kw))
        )
    if tag_value_id:
        q = q.join(MaterialTag, MaterialTag.material_id == Material.id) \
             .filter(MaterialTag.tag_value_id == tag_value_id) \
             .distinct()
    if order == "collects":
        col = Material.collects
    elif order == "latest":
        col = Material.fetched_at
    else:
        col = Material.likes
    q = q.order_by(col.desc())
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [_material_summary(s, m) for m in items],
    }


def _material_summary(s, m):
    tags = s.query(MaterialTag).filter_by(material_id=m.id).all()
    return {
        "id": m.id, "title": m.title, "author": m.author,
        "likes": m.likes, "collects": m.collects, "comments_count": m.comments_count,
        "published_at": m.published_at, "tags_raw": m.tags_raw,
        "image_count": len(m.images),
        "tags": [_tag_view(s, t) for t in tags],
    }


def _tag_view(s, mt):
    tv = s.query(TagValue).get(mt.tag_value_id)
    dim = s.query(TagDimension).get(tv.dimension_id) if tv else None
    return {
        "tag_value_id": mt.tag_value_id,
        "dimension": dim.name if dim else None,
        "value": tv.value if tv else None,
        "source": mt.source,
        "confidence": mt.confidence,
        "confirmed_by_human": mt.confirmed_by_human,
    }


@router.get("/materials/{mid}")
def get_material(mid: int, s: Session = Depends(get_db)):
    m = s.query(Material).get(mid)
    if not m:
        raise HTTPException(404)
    summary = _material_summary(s, m)
    summary.update({
        "content": m.content,
        "url": m.url,
        "local_folder": m.local_folder,
        "images": [{"idx": i.idx, "path": i.path, "type": i.type} for i in m.images],
    })
    return summary


@router.get("/materials/{mid}/image")
def get_image(mid: int, path: str):
    media_root = config.MEDIA_DIR.resolve()
    full = (config.MEDIA_DIR / path).resolve()
    if not full.is_relative_to(media_root) or not full.exists():
        raise HTTPException(404)
    return FileResponse(full)



# spec §5.1 批量打同一标签（必须注册在 /materials/{mid}/tags 之前，
# 否则 batch 被 {mid} 匹配 → 422）
class BatchTagIn(BaseModel):
    material_ids: list[int]
    tag_value_id: int


@router.post("/materials/batch/tags")
def batch_tag(body: BatchTagIn, s: Session = Depends(get_db)):
    added = 0
    for mid in body.material_ids:
        exists = s.query(MaterialTag).filter_by(
            material_id=mid, tag_value_id=body.tag_value_id).first()
        if exists:
            continue
        s.add(MaterialTag(
            material_id=mid, tag_value_id=body.tag_value_id,
            source="human", confidence=None, confirmed_by_human=True,
        ))
        added += 1
    s.commit()
    return {"ok": True, "added": added}


# spec §5.1 右键 chip：改 / 拒绝 / 转为"建议新标签"
class TagActionIn(BaseModel):
    tag_value_id: int
    action: str  # confirm | reject | suggest_new
    new_dimension: str | None = None
    new_value: str | None = None


@router.post("/materials/{mid}/tags")
def manage_material_tag(
    mid: int, body: TagActionIn, s: Session = Depends(get_db)
):
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
    elif body.action == "suggest_new":
        # 移除现有标签，写一条 tag_suggestion 给人 review
        if mt:
            tv = s.query(TagValue).get(mt.tag_value_id)
            dim_name = body.new_dimension or (tv.dimension.name if tv and tv.dimension else "")
            s.delete(mt)
        else:
            dim_name = body.new_dimension or ""
        value = body.new_value or ""
        if value:
            s.add(TagSuggestion(
                dimension_name=dim_name, proposed_value=value,
                material_id=mid, sample_context="", status="pending",
            ))
        s.commit()
        return {"ok": True}
    raise HTTPException(400, "unknown action")
