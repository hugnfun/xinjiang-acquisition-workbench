from datetime import datetime
from sidecar.db.session import session_scope
from sidecar.db.models import (Material, MaterialTag, TagValue, TagDimension,
                               Asset, ScrapeJob)
from sidecar.llm import task_client as tc
from sidecar.jobs.queue import cancellation_checkpoint

# 合成类型 → LLM 返回 dict 的键名
TYPE_KEY = {
    "selling_point": "selling_points",
    "hook": "hooks",
    "cta": "ctas",
    "title": "titles",
}


def _material_data(s, material_ids):
    """组装送入 LLM 的素材数据：标题 / 正文 / dim:value 形式标签。

    返回纯标量 dict 列表，session 关闭后仍可用（不在 MiniMax 调用期间占连接）。
    """
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
    if not material_ids:
        raise ValueError("无素材")
    if job_id and cancellation_checkpoint(job_id):
        return 0
    # 短 session 读素材数据，MiniMax 调用期间不持有 session
    with session_scope() as s:
        mats = _material_data(s, material_ids)
    if not mats:
        raise ValueError("无素材")
    result = tc.synthesize(mats, types)  # 无 session 持有
    if job_id and cancellation_checkpoint(job_id):
        return 0
    written = 0
    asset_tags = sorted({
        tag for material in mats for tag in material.get("tags", [])
    })[:12]
    with session_scope() as s:
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
                    tags=asset_tags,
                    disliked=False,
                ))
                written += 1
    if written == 0:
        raise ValueError("模型没有返回所选类型的有效合成内容")
    if job_id:
        with session_scope() as s:
            job = s.query(ScrapeJob).get(job_id)
            job.status = "done"
            job.result_summary = {"written": written, "types": types}
            job.finished_at = datetime.utcnow()
    return written
