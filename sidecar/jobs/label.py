from datetime import datetime
from pathlib import Path
from sidecar.db.session import session_scope
from sidecar.db.models import (Material, MaterialTag, TagValue, TagDimension,
                               TagSuggestion, ScrapeJob, JobLog)
from sidecar.llm.labeling import label_material
from sidecar.jobs.queue import cancellation_checkpoint
from sidecar import config

CONFIDENCE_THRESHOLD = 0.6

def _taxonomy(s):
    out = []
    for d in s.query(TagDimension).all():
        out.append({"name": d.name, "description": d.description,
                    "values": [v.value for v in d.values if v.status == "active"]})
    return out

def _log(job_id, msg, level="info"):
    """独立短 session 写日志并立即 commit（即时可见 + 不占长连接）。"""
    with session_scope() as s:
        s.add(JobLog(job_id=job_id, level=level, message=msg))

def _set_job(job_id, **fields):
    with session_scope() as s:
        job = s.query(ScrapeJob).get(job_id)
        for k, v in fields.items():
            setattr(job, k, v)

def _write_labels(material_id, material_title, labels):
    """把一篇素材的标签落库（短 session）。返回写入的 MaterialTag 条数。"""
    added = 0
    with session_scope() as s:
        for lb in labels:
            dim_name = lb["dimension"]
            value = lb["value"]
            conf = lb.get("confidence", 0.0)
            if lb.get("out_of_taxonomy"):
                s.add(TagSuggestion(
                    dimension_name=dim_name, proposed_value=value,
                    material_id=material_id, sample_context=material_title[:60],
                    status="pending"))
                continue
            dim = s.query(TagDimension).filter_by(name=dim_name).first()
            if not dim:
                continue
            tv = s.query(TagValue).filter_by(dimension_id=dim.id, value=value).first()
            if not tv:
                s.add(TagSuggestion(dimension_name=dim_name, proposed_value=value,
                                    material_id=material_id, sample_context=material_title[:60],
                                    status="pending"))
                continue
            existing = s.query(MaterialTag).filter_by(material_id=material_id, tag_value_id=tv.id).first()
            if existing:
                continue
            s.add(MaterialTag(
                material_id=material_id, tag_value_id=tv.id, source=lb.get("source", "ai_text"),
                confidence=conf, confirmed_by_human=False))
            added += 1
    return added

def run_label_job(job_id: int):
    _set_job(job_id, status="running", started_at=datetime.utcnow(), progress=0, progress_total=0)
    _log(job_id, "开始批量打标")

    # 短 session 读 taxonomy + 素材，提取标量；LLM 打标期间不持有 session
    with session_scope() as s:
        taxonomy = _taxonomy(s)
        materials = s.query(Material).all()
        mat_data = [{
            "id": m.id, "title": m.title, "content": m.content,
            "images": [img.path for img in m.images[:3]],
        } for m in materials]
    _set_job(job_id, progress_total=len(mat_data))
    labeled = 0
    failed = 0
    last_error = ""
    try:
        for md in mat_data:
            if cancellation_checkpoint(job_id):
                return
            image_paths = [config.MEDIA_DIR / p for p in md["images"]]
            try:
                labels = label_material(md["title"], md["content"], image_paths, taxonomy)
            except Exception as e:
                failed += 1
                last_error = str(e)
                _log(job_id, f"素材 {md['id']} 打标失败: {e}", "error")
                continue
            _write_labels(md["id"], md["title"], labels)
            labeled += 1
            _set_job(job_id, progress=labeled + failed)
            _log(job_id, f"素材 {md['id']} 完成 ({len(labels)} 标签)")
        total = len(mat_data)
        # 全部素材打标失败：暴露失败而非伪装成 done（避免 done+0 隐藏如 API_KEY 缺失）
        if labeled == 0 and failed > 0:
            err = f"全部 {total} 篇素材打标失败，最近错误: {last_error}"
            _set_job(job_id, status="failed", error=err,
                     result_summary={"labeled": 0, "total": total, "failed_count": failed},
                     finished_at=datetime.utcnow())
            _log(job_id, err, "error")
        else:
            summary = {"labeled": labeled, "total": total}
            if failed > 0:
                summary["failed_count"] = failed
            _set_job(job_id, status="done", result_summary=summary, finished_at=datetime.utcnow())
            _log(job_id, f"完成，共 {labeled} 篇" + (f"，{failed} 篇失败" if failed else ""))
    except Exception as e:
        _set_job(job_id, status="failed", error=str(e), finished_at=datetime.utcnow())
        _log(job_id, f"失败: {e}", "error")


def run_relabel_job(job_id: int, material_ids: list[int]):
    """spec §5.1 批量触发 AI 重打标：只对选中素材重新打标。

    与全量打标的区别：先清掉选中素材的 ai_text/ai_vision 标签（保留 human 标签），
    再重新调 LLM 打标。"""
    _set_job(job_id, status="running", started_at=datetime.utcnow(), progress=0, progress_total=0)
    _log(job_id, f"开始重打标：{len(material_ids)} 篇素材")
    with session_scope() as s:
        taxonomy = _taxonomy(s)
        mats = []
        for mid in material_ids:
            m = s.query(Material).get(mid)
            if not m:
                continue
            # 清掉 AI 标签（保留 human 标签）
            ai_tags = s.query(MaterialTag).filter(
                MaterialTag.material_id == mid,
                MaterialTag.source.in_(["ai_text", "ai_vision"]),
            ).all()
            for mt in ai_tags:
                s.delete(mt)
            mats.append({
                "id": m.id, "title": m.title, "content": m.content,
                "images": [img.path for img in m.images[:3]],
            })
    _set_job(job_id, progress_total=len(mats))
    labeled = 0
    failed = 0
    last_error = ""
    try:
        for md in mats:
            if cancellation_checkpoint(job_id):
                return
            image_paths = [config.MEDIA_DIR / p for p in md["images"]]
            try:
                labels = label_material(md["title"], md["content"], image_paths, taxonomy)
            except Exception as e:
                failed += 1
                last_error = str(e)
                _log(job_id, f"素材 {md['id']} 重打标失败: {e}", "error")
                continue
            _write_labels(md["id"], md["title"], labels)
            labeled += 1
            _set_job(job_id, progress=labeled + failed)
            _log(job_id, f"素材 {md['id']} 重打标完成 ({len(labels)} 标签)")
        if labeled == 0 and failed > 0:
            _set_job(job_id, status="failed", error=f"全部 {len(mats)} 篇重打标失败: {last_error}",
                     result_summary={"labeled": 0, "total": len(mats)}, finished_at=datetime.utcnow())
        else:
            _set_job(job_id, status="done",
                     result_summary={"labeled": labeled, "total": len(mats)},
                     finished_at=datetime.utcnow())
            _log(job_id, f"完成，共 {labeled} 篇重打标")
    except Exception as e:
        _set_job(job_id, status="failed", error=str(e), finished_at=datetime.utcnow())
        _log(job_id, f"失败: {e}", "error")
