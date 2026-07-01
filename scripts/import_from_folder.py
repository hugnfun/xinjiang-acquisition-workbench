import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sidecar import config
from sidecar.db.session import init_db, get_session
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

def _note_id_from_url(url: str) -> str:
    m = re.search(r"/search_result/([0-9a-f]+)", url)
    return m.group(1) if m else url

def import_folder(source_dir: Path) -> int:
    source_dir = Path(source_dir)
    init_db()
    manifest = json.loads((source_dir / "_manifest.json").read_text(encoding="utf-8"))
    items = manifest["items"]
    s = get_session()
    count = 0
    for item in items:
        folder = source_dir / item["folder"]
        note_md = folder / "note.md"
        if not note_md.exists():
            continue
        parsed = parse_note_md(note_md.read_text(encoding="utf-8"))
        url = item["url"]
        note_id = _note_id_from_url(url)

        m = Material(
            note_id=note_id,
            url=url,
            title=item.get("title") or parsed.title,
            author=item.get("author") or parsed.metadata.get("作者", ""),
            author_url="",
            content=parsed.content,
            likes=parse_likes(item.get("likes_raw") or parsed.metadata.get("点赞", "0")),
            collects=parse_likes(parsed.metadata.get("收藏", "0")),
            comments_count=parse_likes(parsed.metadata.get("评论数", "0")),
            tags_raw=parsed.metadata.get("标签", ""),
            published_at=item.get("published_at") or parsed.metadata.get("发布时间"),
            local_folder=item["folder"],
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
                s.add(MaterialImage(material_id=m.id, idx=idx, path=str(dst.relative_to(config.MEDIA_DIR)), type="image"))

        for rank, c in enumerate(parsed.comments, 1):
            s.add(Comment(
                material_id=m.id, rank=rank, author=c["author"],
                text=c["text"], likes=c["likes"], time=c["time"],
                is_reply=c["is_reply"], reply_to=c["reply_to"],
            ))
        count += 1
    s.commit()
    return count

if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Users/aicer/Documents/Project/小红书-新疆旅游")
    n = import_folder(src)
    print(f"导入 {n} 篇素材")
