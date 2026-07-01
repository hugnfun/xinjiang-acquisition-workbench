from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sidecar.db.session import get_session
from sidecar.db.models import Material, MaterialTag, TagValue, TagDimension
from sidecar import config

router = APIRouter()

@router.get("/materials")
def list_materials(limit: int = 50, offset: int = 0, order: str = "likes"):
    s = get_session()
    q = s.query(Material)
    col = Material.likes if order == "likes" else Material.fetched_at
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
def get_material(mid: int):
    s = get_session()
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
