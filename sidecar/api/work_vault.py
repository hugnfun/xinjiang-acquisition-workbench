"""Work Vault 导入 API：dry-run 扫描 + 批量导入。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sidecar.db.session import get_db
from sidecar.db.models import Material, ScrapeJob
from sidecar.importers.work_vault import scan_vault, backfill_work_vault_authors
from sidecar.jobs.queue import submit
from sidecar.jobs.work_vault import run_work_vault_import

router = APIRouter()

DEFAULT_VAULT_DIR = "/Users/aicer/Documents/Work Vault"


class ScanIn(BaseModel):
    vault_dir: str = DEFAULT_VAULT_DIR


class ImportIn(BaseModel):
    vault_dir: str = DEFAULT_VAULT_DIR
    filenames: list[str]


class BackfillAuthorsIn(BaseModel):
    vault_dir: str = DEFAULT_VAULT_DIR
    dry_run: bool = True


@router.post("/work-vault/scan")
def scan(body: ScanIn, s: Session = Depends(get_db)):
    """只读扫描 Work Vault，返回每篇笔记的分类预览。

    不会写入任何数据，用于导入前的 dry-run 验收。
    """
    # 收集 DB 中已有 Work Vault 素材的 content_hash（note_id）
    existing = set()
    for m in s.query(Material).filter(
        Material.local_folder.like("workvault:%")
    ).all():
        existing.add(m.note_id)

    try:
        items = scan_vault(body.vault_dir, existing)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))

    return {
        "vault_dir": body.vault_dir,
        "total_files": len(items),
        "summary": _summarize(items),
        "items": [_item_to_dict(i) for i in items],
    }


@router.post("/work-vault/import")
def import_notes(body: ImportIn, s: Session = Depends(get_db)):
    """批量导入选定的 Work Vault 笔记（异步 job）。"""
    if not body.filenames:
        raise HTTPException(400, "filenames 不能为空")

    job = ScrapeJob(
        type="work_vault_import",
        status="queued",
        params={"vault_dir": body.vault_dir, "filenames": body.filenames},
    )
    s.add(job)
    s.commit()
    s.refresh(job)
    submit(job.id, run_work_vault_import, job.id, body.vault_dir, body.filenames)
    return {"job_id": job.id}


@router.post("/work-vault/backfill-authors")
def backfill_authors(
    body: BackfillAuthorsIn, s: Session = Depends(get_db)
):
    """预览或执行 Work Vault 空作者回填，不覆盖已有作者。"""
    try:
        result = backfill_work_vault_authors(
            s, body.vault_dir, dry_run=body.dry_run
        )
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    if not body.dry_run:
        s.commit()
    return result


def _summarize(items) -> dict:
    counts: dict[str, int] = {}
    for i in items:
        counts[i.status] = counts.get(i.status, 0) + 1
    return counts


def _item_to_dict(i) -> dict:
    return {
        "filename": i.filename,
        "title": i.title,
        "status": i.status,
        "content_hash": i.content_hash,
        "image_count": i.image_count,
        "image_missing": i.image_missing,
        "comment_count_declared": i.comment_count_declared,
        "comment_count_parsed": i.comment_count_parsed,
        "body_preview": i.body_preview,
        "tags_raw": i.tags_raw,
        "published_at": i.published_at,
        "duplicate_of": i.duplicate_of,
    }
