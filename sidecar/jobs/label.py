from datetime import datetime
from pathlib import Path
from sidecar.db.session import get_session
from sidecar.db.models import (Material, MaterialTag, TagValue, TagDimension,
                               TagSuggestion, ScrapeJob, JobLog)
from sidecar.llm.labeling import label_material
from sidecar import config

CONFIDENCE_THRESHOLD = 0.6

def _taxonomy(s):
    out = []
    for d in s.query(TagDimension).all():
        out.append({"name": d.name, "description": d.description,
                    "values": [v.value for v in d.values if v.status == "active"]})
    return out

def _log(s, job_id, msg, level="info"):
    s.add(JobLog(job_id=job_id, level=level, message=msg))

def run_label_job(job_id: int):
    s = get_session()
    job = s.query(ScrapeJob).get(job_id)
    job.status = "running"
    job.started_at = datetime.utcnow()
    _log(s, job_id, "开始批量打标")
    s.commit()

    taxonomy = _taxonomy(s)
    materials = s.query(Material).all()
    labeled = 0
    failed = 0
    last_error = ""
    try:
        for m in materials:
            image_paths = [config.MEDIA_DIR / img.path for img in m.images[:3]]
            try:
                labels = label_material(m.title, m.content, image_paths, taxonomy)
            except Exception as e:
                failed += 1
                last_error = str(e)
                _log(s, job_id, f"素材 {m.id} 打标失败: {e}", "error")
                s.commit()
                continue
            for lb in labels:
                dim_name = lb["dimension"]
                value = lb["value"]
                conf = lb.get("confidence", 0.0)
                if lb.get("out_of_taxonomy"):
                    s.add(TagSuggestion(
                        dimension_name=dim_name, proposed_value=value,
                        material_id=m.id, sample_context=m.title[:60],
                        status="pending"))
                    continue
                dim = s.query(TagDimension).filter_by(name=dim_name).first()
                if not dim:
                    continue
                tv = s.query(TagValue).filter_by(dimension_id=dim.id, value=value).first()
                if not tv:
                    s.add(TagSuggestion(dimension_name=dim_name, proposed_value=value,
                                        material_id=m.id, sample_context=m.title[:60], status="pending"))
                    continue
                existing = s.query(MaterialTag).filter_by(material_id=m.id, tag_value_id=tv.id).first()
                if existing:
                    continue
                s.add(MaterialTag(
                    material_id=m.id, tag_value_id=tv.id, source=lb.get("source", "ai_text"),
                    confidence=conf, confirmed_by_human=False))
            labeled += 1
            _log(s, job_id, f"素材 {m.id} 完成 ({len(labels)} 标签)")
            s.commit()
        total = len(materials)
        # 全部素材打标失败：暴露失败而非伪装成 done（避免 done+0 隐藏如 ANTHROPIC_API_KEY 缺失）
        if labeled == 0 and failed > 0:
            job.status = "failed"
            job.error = f"全部 {total} 篇素材打标失败，最近错误: {last_error}"
            job.result_summary = {"labeled": 0, "total": total, "failed_count": failed}
            _log(s, job_id, job.error, "error")
        else:
            job.status = "done"
            job.result_summary = {"labeled": labeled, "total": total}
            if failed > 0:
                job.result_summary["failed_count"] = failed
                _log(s, job_id, f"完成，共 {labeled} 篇，{failed} 篇失败")
            else:
                _log(s, job_id, f"完成，共 {labeled} 篇")
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        _log(s, job_id, f"失败: {e}", "error")
    finally:
        job.finished_at = datetime.utcnow()
        s.commit()
