from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import func, and_
from sidecar.db.session import get_db
from sidecar.db.models import (
    Material, MaterialTag, MaterialImage, TagValue, TagDimension, TagSuggestion,
)
from sidecar import config

router = APIRouter()


@router.get("/materials")
def list_materials(
    limit: int = 30, offset: int = 0, order: str = "likes",
    search: str | None = None,
    tag_value_id: int | None = None,
    tag_value_ids: str | None = None,
    completeness: str | None = None,
    s: Session = Depends(get_db),
):
    """素材列表。

    tag_value_ids: 逗号分隔的 tag_value_id 列表，AND 筛选（必须同时有所有标签）。
    completeness: missing_url | missing_images | unlabeled | pending_review
    """
    q = s.query(Material)

    if search:
        kw = f"%{search.strip()}%"
        q = q.filter(
            (Material.title.like(kw)) | (Material.content.like(kw)) | (Material.author.like(kw))
        )

    # 单标签筛选（向后兼容）
    if tag_value_id:
        q = q.join(MaterialTag, MaterialTag.material_id == Material.id) \
             .filter(MaterialTag.tag_value_id == tag_value_id) \
             .distinct()

    # 多维标签筛选（AND 逻辑）
    if tag_value_ids:
        ids = [int(x) for x in tag_value_ids.split(",") if x.strip()]
        if len(ids) == 1:
            q = q.join(MaterialTag, MaterialTag.material_id == Material.id) \
                 .filter(MaterialTag.tag_value_id == ids[0]).distinct()
        elif ids:
            # 必须同时拥有所有指定标签
            q = q.join(MaterialTag, MaterialTag.material_id == Material.id) \
                 .filter(MaterialTag.tag_value_id.in_(ids)) \
                 .group_by(Material.id) \
                 .having(func.count(func.distinct(MaterialTag.tag_value_id)) == len(ids))

    # 数据完整度筛选
    if completeness == "missing_url":
        q = q.filter((Material.url == "") | (Material.url.is_(None)))
    elif completeness == "missing_images":
        q = q.filter(~Material.id.in_(
            s.query(MaterialImage.material_id).distinct()
        ))
    elif completeness == "unlabeled":
        q = q.filter(~Material.id.in_(
            s.query(MaterialTag.material_id).distinct()
        ))
    elif completeness == "pending_review":
        q = q.join(MaterialTag, MaterialTag.material_id == Material.id) \
             .filter(MaterialTag.confirmed_by_human == False) \
             .distinct()

    if order == "collects":
        col = Material.collects
    elif order == "latest":
        col = Material.fetched_at
    else:
        col = Material.likes
    q = q.order_by(col.desc())

    total = q.count()
    items = q.options(
        selectinload(Material.tags).joinedload(MaterialTag.tag_value).joinedload(TagValue.dimension)
    ).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [_material_summary(m) for m in items],
    }


def _material_summary(m: Material):
    """从已 eager-load 的 Material 构建摘要，不再额外查询。"""
    tags = []
    for t in m.tags:
        tv = t.tag_value
        if not tv:
            continue
        dim = tv.dimension
        tags.append({
            "tag_value_id": t.tag_value_id,
            "dimension": dim.name if dim else None,
            "value": tv.value,
            "source": t.source,
            "confidence": t.confidence,
            "confirmed_by_human": t.confirmed_by_human,
        })
    return {
        "id": m.id, "title": m.title, "author": m.author,
        "likes": m.likes, "collects": m.collects, "comments_count": m.comments_count,
        "published_at": m.published_at, "tags_raw": m.tags_raw,
        "image_count": len(m.images),
        "tags": tags,
    }


@router.get("/materials/{mid}")
def get_material(mid: int, s: Session = Depends(get_db)):
    m = s.query(Material).options(
        selectinload(Material.tags).joinedload(MaterialTag.tag_value).joinedload(TagValue.dimension)
    ).get(mid)
    if not m:
        raise HTTPException(404)
    summary = _material_summary(m)
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


# spec §5.1 批量打同一标签
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
