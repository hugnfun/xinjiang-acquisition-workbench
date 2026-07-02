"""关键词抓取 job：opencli search → 逐条 download → 复用 insert_note 入库。

spec §8 v0.3 项「抓取任务表单 UI（UI 内触发新关键词抓取）」的 job 侧。
LLM/网络调用期间不持有 session（C1 模式），逐条 try/except 不中断整批。
"""
from datetime import datetime
from sidecar.db.session import session_scope
from sidecar.db.models import ScrapeJob, JobLog
from sidecar.opencli import runner
from sidecar.importers.note_importer import insert_note, note_id_from_url
from sidecar import config


def _log(job_id, msg, level="info"):
    with session_scope() as s:
        s.add(JobLog(job_id=job_id, level=level, message=msg))


def _set_job(job_id, **fields):
    with session_scope() as s:
        job = s.query(ScrapeJob).get(job_id)
        for k, v in fields.items():
            setattr(job, k, v)


def run_scrape_job(job_id: int, keyword: str, limit: int = 20):
    _set_job(job_id, status="running", started_at=datetime.utcnow())
    _log(job_id, f"开始抓取：关键词「{keyword}」上限 {limit}")
    imported = 0
    failed = 0
    total = 0
    try:
        results = runner.search(keyword, limit)
        total = len(results)
        _log(job_id, f"搜索到 {total} 条结果")
        base = config.MEDIA_DIR / "scrapes" / str(job_id)
        for r in results:
            url = r.get("url")
            if not url:
                continue
            nid = note_id_from_url(url)
            folder = base / nid
            folder.mkdir(parents=True, exist_ok=True)
            # download → 文件夹(note.md + images/)；失败/无 note.md 则跳过该条
            try:
                runner.download(url, str(folder))
            except Exception as e:
                failed += 1
                _log(job_id, f"下载失败 {nid}: {e}", "error")
                continue
            item = {
                "url": url, "title": r.get("title", ""), "author": r.get("author", ""),
                "author_url": r.get("author_url", ""), "likes": r.get("likes", "0"),
                "published_at": r.get("published_at"), "folder": str(folder),
            }
            try:
                with session_scope() as s:
                    ok = insert_note(s, folder, item)
                if ok:
                    imported += 1
                    _log(job_id, f"已入库 {nid}: {(r.get('title') or '')[:30]}")
                else:
                    failed += 1
                    _log(job_id, f"跳过 {nid}: 无 note.md", "error")
            except Exception as e:
                failed += 1
                _log(job_id, f"入库失败 {nid}: {e}", "error")
        _set_job(job_id, status="done",
                 result_summary={"imported": imported, "failed": failed, "total": total},
                 finished_at=datetime.utcnow())
        _log(job_id, f"完成：入库 {imported}，失败 {failed}，共 {total}")
    except Exception as e:
        _set_job(job_id, status="failed", error=str(e), finished_at=datetime.utcnow())
        _log(job_id, f"失败: {e}", "error")
