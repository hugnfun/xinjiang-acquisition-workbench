import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sidecar.db.session import init_db, session_scope
from sidecar.importers.note_importer import insert_note


def import_folder(source_dir: Path) -> int:
    """批量导入已抓取文件夹（_manifest.json + 各 folder/note.md + images/）。"""
    source_dir = Path(source_dir)
    init_db()
    manifest = json.loads((source_dir / "_manifest.json").read_text(encoding="utf-8"))
    count = 0
    with session_scope() as s:
        for item in manifest["items"]:
            folder = source_dir / item["folder"]
            if insert_note(s, folder, item):
                count += 1
    return count


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Users/aicer/Documents/Project/小红书-新疆旅游")
    n = import_folder(src)
    print(f"导入 {n} 篇素材")
