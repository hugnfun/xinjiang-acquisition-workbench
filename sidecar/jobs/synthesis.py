from datetime import datetime
from sidecar.db.session import get_session
from sidecar.db.models import (Material, MaterialTag, TagValue, TagDimension,
                               Asset, ScrapeJob, JobLog)
from sidecar.llm import task_client as tc

# 合成类型 → LLM 返回 dict 的键名
TYPE_KEY = {
    "selling_point": "selling_points",
    "hook": "hooks",
    "cta": "ctas",
    "title": "titles",
}


def _material_data(s, material_ids):
    """组装送入 LLM 的素材数据：标题 / 正文 / dim:value 形式标签。"""
    out = []
    for mid in material_ids:
        m = s.query(Material).get(mid)
        if not m:
            continue
        mts = s.query(MaterialTag).filter_by(material_id=mid).all()
        tags = []
        for mt in mts:
            tv = s.query(TagValue).get(mt.tag_value_id)
            dim = s.query(TagDimension).get(tv.dimension_id) if tv else None
            if tv and dim:
                tags.append(f"{dim.name}:{tv.value}")
        out.append({"id": m.id, "title": m.title, "content": m.content, "tags": tags})
    return out


def run_synthesis(material_ids: list[int], types: list[str], job_id: int | None = None):
    s = get_session()
    if not material_ids:
        raise ValueError("无素材")
    mats = _material_data(s, material_ids)
    if not mats:
        raise ValueError("无素材")
    result = tc.synthesize(mats, types)
    written = 0
    for t in types:
        key = TYPE_KEY.get(t)
        if not key:
            continue
        for text in result.get(key, []):
            if not text or not text.strip():
                continue
            s.add(Asset(
                type=t, text=text.strip(),
                derived_from=list(material_ids),
                tags=[m["title"][:20] for m in mats[:3]],
                disliked=False,
            ))
            written += 1
    s.commit()
    if job_id:
        job = s.query(ScrapeJob).get(job_id)
        job.status = "done"
        job.result_summary = {"written": written, "types": types}
        job.finished_at = datetime.utcnow()
        s.commit()
    return written
