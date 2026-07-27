from datetime import datetime
from sidecar.db.session import session_scope
from sidecar.db.models import (Material, MaterialTag, TagValue, TagDimension,
                               Asset, ScrapeJob)
from sidecar.llm import task_client as tc
from sidecar.jobs.queue import cancellation_checkpoint
from sidecar.jobs.usage import job_usage_accumulator
from sidecar import config

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


def _allocate_usage(usage: dict, count: int) -> list[dict]:
    """把一次合成调用的 usage 精确分配给 N 条 Asset，整数余数按顺序分配。"""
    if count <= 0:
        return []
    rows = []
    token_fields = ("prompt_tokens", "completion_tokens", "total_tokens")
    bases = {field: int(usage.get(field, 0) or 0) // count for field in token_fields}
    remainders = {field: int(usage.get(field, 0) or 0) % count for field in token_fields}
    total_cost = usage.get("cost_cny")
    cost_base = round(float(total_cost) / count, 8) if total_cost is not None else None
    for index in range(count):
        row = {
            **{field: bases[field] + (1 if index < remainders[field] else 0)
               for field in token_fields},
            "cost_cny": cost_base,
            "available": bool(usage.get("available")),
            "provider": usage.get("provider"),
            "model": usage.get("model"),
            "allocation_method": "equal",
        }
        rows.append(row)
    if total_cost is not None and rows:
        allocated = sum(row["cost_cny"] or 0 for row in rows[:-1])
        rows[-1]["cost_cny"] = round(float(total_cost) - allocated, 8)
    return rows


def run_synthesis(material_ids: list[int], types: list[str], job_id: int | None = None):
    usage = job_usage_accumulator(job_id)
    with tc.track_usage(usage):
        return _run_synthesis(material_ids, types, job_id, usage)


def _run_synthesis(
    material_ids: list[int],
    types: list[str],
    job_id: int | None,
    usage,
):
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
    asset_tags = sorted({
        tag for material in mats for tag in material.get("tags", [])
    })[:12]
    candidates: list[tuple[str, str]] = []
    with session_scope() as s:
        for t in types:
            key = TYPE_KEY.get(t)
            if not key:
                continue
            for text in result.get(key, []):
                if not text or not text.strip():
                    continue
                clean = text.strip()
                # 去重：同类型同文本已存在则跳过
                exists = s.query(Asset).filter_by(type=t, text=clean).first()
                if exists:
                    continue
                candidates.append((t, clean))
    written = len(candidates)
    if written == 0:
        raise ValueError("模型没有返回所选类型的有效合成内容")
    allocations = _allocate_usage(usage.to_dict(), written)
    with session_scope() as s:
        for (t, clean), allocation in zip(candidates, allocations):
            s.add(Asset(
                type=t, text=clean,
                derived_from=list(material_ids),
                tags=asset_tags,
                disliked=False,
                source_job_id=job_id,
                model_name=config.TASK_MODEL,
                prompt_version="synthesis-v1",
                token_usage=allocation,
            ))
    if job_id:
        with session_scope() as s:
            job = s.query(ScrapeJob).get(job_id)
            job.status = "done"
            job.result_summary = {"written": written, "types": types}
            job.finished_at = datetime.utcnow()
    return written
