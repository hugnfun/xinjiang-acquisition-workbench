"""单条 note 文件夹(note.md + images/)→ DB 行的入库逻辑。

抽自 scripts/import_from_folder.py，供「文件夹批量导入」和「关键词抓取 job」复用。
item dict 兼容两种来源：manifest 项(likes_raw/folder) 与 opencli search 结果(likes/author_url)。
"""
import re
import shutil
import hashlib
from pathlib import Path

from sidecar import config
from sidecar.db.models import Material, MaterialImage, Comment
from sidecar.importers.note_md import parse_note_md

_LIKE_RE = re.compile(r"^([\d.]+)\s*([万wW]?)$")


def parse_likes(s: str) -> int:
    if not s:
        return 0
    s = str(s).replace(",", "").replace("+", "").strip()
    m = _LIKE_RE.match(s)
    if not m:
        try:
            return int(float(s))
        except Exception:
            return 0
    n = float(m.group(1))
    if m.group(2) in ("万", "w", "W"):
        n *= 10000
    return int(n)


def note_id_from_url(url: str) -> str:
    m = re.search(r"/(?:search_result|explore)/([0-9a-fA-F]+)", url)
    if m:
        return m.group(1).lower()
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:32]


def insert_note(s, folder, item: dict) -> bool:
    """把单个 note 文件夹(note.md + images/)写入 DB。

    folder: 含 note.md 的目录；item: {url, title?, author?, author_url?, likes/likes_raw?,
    published_at?, folder?}。不 commit（由调用方控制事务）。返回是否成功插入。
    """
    folder = Path(folder)
    note_md = folder / "note.md"
    if not note_md.exists():
        return False
    parsed = parse_note_md(note_md.read_text(encoding="utf-8"))
    url = item["url"]
    note_id = note_id_from_url(url)
    if s.query(Material).filter_by(
        platform="xiaohongshu", note_id=note_id
    ).first():
        return False

    m = Material(
        note_id=note_id,
        url=url,
        title=item.get("title") or parsed.title,
        author=item.get("author") or parsed.metadata.get("作者", ""),
        author_url=item.get("author_url", ""),
        content=parsed.content,
        likes=parse_likes(item.get("likes_raw") or item.get("likes") or parsed.metadata.get("点赞", "0")),
        collects=parse_likes(parsed.metadata.get("收藏", "0")),
        comments_count=parse_likes(parsed.metadata.get("评论数", "0")),
        tags_raw=parsed.metadata.get("标签", ""),
        published_at=item.get("published_at") or parsed.metadata.get("发布时间"),
        local_folder=str(item.get("folder", "")),
    )
    s.add(m); s.flush()

    # 复制图片到 data/media/<note_id>/
    media_dst = config.MEDIA_DIR / note_id
    media_dst.mkdir(parents=True, exist_ok=True)
    for idx, rel in enumerate(parsed.image_paths):
        src = folder / rel
        if src.exists():
            dst = media_dst / src.name
            shutil.copy2(src, dst)
            s.add(MaterialImage(material_id=m.id, idx=idx,
                               path=str(dst.relative_to(config.MEDIA_DIR)), type="image"))

    for rank, c in enumerate(parsed.comments, 1):
        s.add(Comment(
            material_id=m.id, rank=rank, author=c["author"],
            text=c["text"], likes=c["likes"], time=c["time"],
            is_reply=c["is_reply"], reply_to=c["reply_to"],
        ))
    return True
