"""Work Vault 导入 job：批量导入 Obsidian 笔记到 DB。

通过统一任务队列串行执行，写入进度和日志。
"""
from sidecar.db.session import session_scope
from sidecar.db.models import ScrapeJob, Material
from sidecar.jobs.queue import cancellation_checkpoint, _append_log, _update_job
from sidecar.importers.work_vault import insert_work_vault_note


def run_work_vault_import(job_id: int, vault_dir: str, filenames: list[str]):
    """串行导入指定文件列表，写入进度和日志。"""
    total = len(filenames)
    _update_job(job_id, progress=0, progress_total=total)
    _append_log(job_id, f"开始导入 {total} 篇 Work Vault 笔记")

    imported = 0
    skipped = 0
    failed = 0

    for idx, fn in enumerate(filenames, 1):
        if cancellation_checkpoint(job_id):
            _append_log(job_id, "任务已取消", "warning")
            break

        try:
            with session_scope() as s:
                ok = insert_work_vault_note(s, vault_dir, fn)
            if ok:
                imported += 1
                _append_log(job_id, f"[{idx}/{total}] 导入成功: {fn}")
            else:
                skipped += 1
                _append_log(job_id, f"[{idx}/{total}] 跳过(重复或无效): {fn}")
        except Exception as e:
            failed += 1
            _append_log(job_id, f"[{idx}/{total}] 失败: {fn} - {e}", "error")

        _update_job(job_id, progress=idx)

    summary = {"imported": imported, "skipped": skipped, "failed": failed, "total": total}
    _update_job(
        job_id,
        status="done" if failed == 0 else "failed",
        result_summary=summary,
        error=None if failed == 0 else f"{failed} 篇导入失败",
        finished_at=__import__("datetime").datetime.utcnow(),
    )
    _append_log(job_id, f"完成: 导入 {imported} / 跳过 {skipped} / 失败 {failed}")
    return summary
