"""Work Vault 导入专用解析器。

Work Vault 是用户的 Obsidian 笔记库，扁平 .md + 散落 Pasted image*.png。
格式与 OpenCLI 的 note.md 完全不同，独立实现，不污染 note_md.py。

解析流程：
1. 从 .md 文本中提取图片引用（Obsidian ![[...]] 语法）
2. 以 "共 N 条评论" 为界分离正文与评论区
3. 从正文尾部提取标签、猜你想搜、编辑日期
4. 从评论区按块解析每条评论
5. 用标题+正文前缀算 content_hash 作为 note_id，用于跨 DB 去重
"""
import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from sidecar import config
from sidecar.db.models import Material, MaterialImage, Comment

# ── 正则 ──

_OBS_IMG_RE = re.compile(r"!\[\[([^\]]+\.png)\]\]")
_MD_TAG_RE = re.compile(r"\[#([^\]]+)\]\([^)]*\)")
_PLAIN_TAG_RE = re.compile(r"#([^\s#]+)")
_COMMENT_COUNT_RE = re.compile(r"共\s*(\d+)\s*条评论")
_EDIT_DATE_RE = re.compile(r"编辑于\s+(\d{4}-\d{2}-\d{2}|\d{2}-\d{2})")
_STANDALONE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$", re.M)
_COMMENT_DATE_RE = re.compile(
    r"^(?:"
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{2}-\d{2}"
    r"|\d+小时前"
    r"|昨天\s*\d{2}:\d{2}"
    r"|前天\s*\d{2}:\d{2}"
    r"|\d+天前"
    r"|刚刚"
    r")"
)


@dataclass
class ParsedWorkVaultNote:
    """单篇 Work Vault 笔记的解析结果。"""
    filename: str = ""
    title: str = ""
    content: str = ""
    tags_raw: str = ""
    published_at: str = ""
    comments_count: int = 0
    image_refs: list[str] = field(default_factory=list)
    comments: list[dict] = field(default_factory=list)
    content_hash: str = ""
    is_empty: bool = False
    is_note: bool = True
    raw_size: int = 0


# ── 正文与元数据提取 ──

def _extract_images(text):
    """提取 ![[...]] 图片引用并从文本中移除。"""
    refs = _OBS_IMG_RE.findall(text)
    cleaned = _OBS_IMG_RE.sub("", text)
    return refs, cleaned


def _extract_tags(text):
    """提取标签，返回 ", #tag1, #tag2" 格式和清理后的文本。"""
    tags = []
    for m in _MD_TAG_RE.finditer(text):
        tags.append(m.group(1))
    text = _MD_TAG_RE.sub("", text)
    for m in _PLAIN_TAG_RE.finditer(text):
        tag = m.group(1)
        if tag not in tags:
            tags.append(tag)
    text = _PLAIN_TAG_RE.sub("", text)
    tags_raw = ", ".join("#" + t for t in tags) if tags else ""
    return tags_raw, text.strip()


def _extract_search_hint(text):
    """移除 "猜你想搜" 块。"""
    idx = text.find("猜你想搜")
    if idx < 0:
        return text
    after = text[idx:]
    lines = after.splitlines()
    cut = 1
    for line in lines[1:]:
        s = line.strip()
        if not s or _COMMENT_COUNT_RE.search(s) or _EDIT_DATE_RE.search(s) or _STANDALONE_DATE_RE.match(s):
            break
        cut += 1
    return (text[:idx] + "\n".join(lines[cut:])).strip()


def _extract_published_at(text):
    """提取发布日期，返回 (日期, 清理后文本)。"""
    m = _EDIT_DATE_RE.search(text)
    if m:
        date = m.group(1)
        text = _EDIT_DATE_RE.sub("", text)
        if not date.startswith("20"):
            date = "2025-" + date
        return date, text.strip()
    m = _STANDALONE_DATE_RE.search(text)
    if m:
        date = m.group(1)
        text = _STANDALONE_DATE_RE.sub("", text, count=1)
        return date, text.strip()
    return "", text.strip()


def _split_body_comments(text):
    """以 "共 N 条评论" 为界分离正文和评论区。"""
    m = _COMMENT_COUNT_RE.search(text)
    if not m:
        return text.strip(), "", 0
    count = int(m.group(1))
    body = text[:m.start()].strip()
    comments_text = text[m.end():].strip()
    return body, comments_text, count


# ── 评论解析 ──

def _parse_comments(block):
    """解析 Work Vault 格式的评论区。

    每条评论由空行分隔，格式：
        <作者名>
        [作者]           <- 可选
        <评论正文>        <- 可空，可多行
        [置顶评论]       <- 可选
        <时间><地点>     <- 2025-05-29北京 / 07-03江苏 / 2小时前陕西
        <点赞数>         <- 数字或 "赞"(=0)
        <回复数>         <- 数字或 "回复"(=0)
        [展开 N 条回复]  <- 可选
    """
    comments = []
    lines = block.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line == "- THE END -":
            break
        if line.startswith("说点什么"):
            i += 1
            while i < n and (lines[i].strip().isdigit() or not lines[i].strip()):
                i += 1
            break
        if line.startswith("展开 "):
            i += 1
            continue

        author = line
        i += 1
        is_author = False
        is_pinned = False
        text_lines = []

        if i < n and lines[i].strip() == "作者":
            is_author = True
            i += 1

        while i < n:
            l = lines[i].strip()
            if not l:
                i += 1
                break
            if l == "置顶评论":
                is_pinned = True
                i += 1
                continue
            if _COMMENT_DATE_RE.match(l):
                break
            if l == "赞" or l == "回复" or l.isdigit():
                break
            if l.startswith("展开 "):
                break
            text_lines.append(l)
            i += 1

        time_str = ""
        if i < n and _COMMENT_DATE_RE.match(lines[i].strip()):
            time_str = lines[i].strip()
            i += 1

        likes = 0
        if i < n:
            l = lines[i].strip()
            if l == "赞":
                likes = 0
                i += 1
            elif l.isdigit():
                likes = int(l)
                i += 1

        if i < n:
            l = lines[i].strip()
            if l == "回复" or l.isdigit():
                i += 1
        if i < n and lines[i].strip().startswith("展开 "):
            i += 1

        comments.append({
            "author": author,
            "text": " ".join(text_lines),
            "likes": likes,
            "time": time_str,
            "is_author": is_author,
            "is_pinned": is_pinned,
        })

    return comments


# ── 主解析函数 ──

def parse_work_vault_note(text, filename=""):
    """解析单篇 Work Vault Obsidian 笔记。"""
    result = ParsedWorkVaultNote(
        filename=filename,
        title=Path(filename).stem if filename else "",
        raw_size=len(text),
    )

    stripped = text.strip()
    if not stripped:
        result.is_empty = True
        result.is_note = False
        return result

    # 判断是否为参考文件（非真实笔记，如 "新疆旅游类型-人设.md"）
    lines_ne = [l for l in stripped.splitlines() if l.strip()]
    if len(lines_ne) <= 25 and all(len(l.strip()) <= 10 for l in lines_ne) and "共" not in stripped:
        result.is_note = False
        result.content = stripped
        return result

    image_refs, cleaned = _extract_images(text)
    body, comments_text, comments_count = _split_body_comments(cleaned)
    published_at, body = _extract_published_at(body)
    body = _extract_search_hint(body)
    tags_raw, body = _extract_tags(body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    comments = _parse_comments(comments_text)

    hash_src = body[:200]
    content_hash = hashlib.sha256(hash_src.encode("utf-8")).hexdigest()[:32]

    result.content = body
    result.tags_raw = tags_raw
    result.published_at = published_at
    result.comments_count = comments_count
    result.image_refs = image_refs
    result.comments = comments
    result.content_hash = content_hash
    return result


# ── dry-run 扫描 ──

@dataclass
class ScanItem:
    """扫描预览中的单条结果。"""
    filename: str
    title: str
    status: str  # valid | duplicate_db | duplicate_vault | empty | non_note | missing_images
    content_hash: str
    image_count: int
    image_missing: list
    comment_count_declared: int
    comment_count_parsed: int
    body_preview: str
    tags_raw: str
    published_at: str
    duplicate_of: str = ""


def scan_vault(vault_dir, existing_hashes=None):
    """只读扫描 Work Vault，返回每篇笔记的分类预览。

    existing_hashes: DB 中已有 Material 的 content_hash 集合。
    """
    vault = Path(vault_dir)
    if not vault.is_dir():
        raise FileNotFoundError("Work Vault 目录不存在: " + vault_dir)

    md_files = sorted(vault.glob("*.md"))
    seen_hashes = {}
    items = []

    for md in md_files:
        text = md.read_text(encoding="utf-8")
        parsed = parse_work_vault_note(text, md.name)

        if parsed.is_empty:
            items.append(ScanItem(
                filename=md.name, title=md.stem, status="empty",
                content_hash="", image_count=0, image_missing=[],
                comment_count_declared=0, comment_count_parsed=0,
                body_preview="", tags_raw="", published_at="",
            ))
            continue

        if not parsed.is_note:
            items.append(ScanItem(
                filename=md.name, title=md.stem, status="non_note",
                content_hash=parsed.content_hash, image_count=0,
                image_missing=[], comment_count_declared=0,
                comment_count_parsed=0, body_preview=parsed.content[:100],
                tags_raw="", published_at="",
            ))
            continue

        img_missing = [ref for ref in parsed.image_refs if not (vault / ref).exists()]

        if existing_hashes and parsed.content_hash in existing_hashes:
            items.append(ScanItem(
                filename=md.name, title=parsed.title, status="duplicate_db",
                content_hash=parsed.content_hash,
                image_count=len(parsed.image_refs), image_missing=img_missing,
                comment_count_declared=parsed.comments_count,
                comment_count_parsed=len(parsed.comments),
                body_preview=parsed.content[:100], tags_raw=parsed.tags_raw,
                published_at=parsed.published_at, duplicate_of="database",
            ))
            seen_hashes[parsed.content_hash] = md.name
            continue

        if parsed.content_hash in seen_hashes:
            items.append(ScanItem(
                filename=md.name, title=parsed.title, status="duplicate_vault",
                content_hash=parsed.content_hash,
                image_count=len(parsed.image_refs), image_missing=img_missing,
                comment_count_declared=parsed.comments_count,
                comment_count_parsed=len(parsed.comments),
                body_preview=parsed.content[:100], tags_raw=parsed.tags_raw,
                published_at=parsed.published_at,
                duplicate_of=seen_hashes[parsed.content_hash],
            ))
            continue

        status = "valid"
        if img_missing:
            status = "missing_images"

        items.append(ScanItem(
            filename=md.name, title=parsed.title, status=status,
            content_hash=parsed.content_hash,
            image_count=len(parsed.image_refs), image_missing=img_missing,
            comment_count_declared=parsed.comments_count,
            comment_count_parsed=len(parsed.comments),
            body_preview=parsed.content[:100], tags_raw=parsed.tags_raw,
            published_at=parsed.published_at,
        ))
        seen_hashes[parsed.content_hash] = md.name

    return items


# ── 入库 ──

def extract_material_author(comments: list[dict]) -> str:
    """从评论区提取笔记作者：优先置顶作者评论，再降级为任意作者评论。"""
    for comment in comments:
        if comment.get("is_author") and comment.get("is_pinned"):
            return (comment.get("author") or "").strip()
    for comment in comments:
        if comment.get("is_author"):
            return (comment.get("author") or "").strip()
    return ""


def backfill_work_vault_authors(s, vault_dir: str, dry_run: bool = True) -> dict:
    """重读 Work Vault 原文件，只为 author 为空的素材补作者。"""
    vault = Path(vault_dir)
    if not vault.is_dir():
        raise FileNotFoundError(f"目录不存在: {vault_dir}")
    materials = s.query(Material).filter(
        Material.local_folder.like("workvault:%"),
        Material.author == "",
    ).order_by(Material.id).all()
    result = {
        "dry_run": dry_run,
        "total_blank": len(materials),
        "repairable": 0,
        "updated": 0,
        "no_author": 0,
        "missing_file": 0,
        "items": [],
    }
    vault_root = vault.resolve()
    for material in materials:
        filename = (material.local_folder or "")[len("workvault:"):]
        source = (vault / filename).resolve()
        try:
            source.relative_to(vault_root)
        except ValueError:
            result["missing_file"] += 1
            result["items"].append({
                "material_id": material.id, "filename": filename,
                "status": "invalid_path", "author": "",
            })
            continue
        if not source.is_file():
            result["missing_file"] += 1
            result["items"].append({
                "material_id": material.id, "filename": filename,
                "status": "missing_file", "author": "",
            })
            continue
        parsed = parse_work_vault_note(
            source.read_text(encoding="utf-8"), filename
        )
        author = extract_material_author(parsed.comments)
        if not author:
            result["no_author"] += 1
            result["items"].append({
                "material_id": material.id, "filename": filename,
                "status": "no_author", "author": "",
            })
            continue
        result["repairable"] += 1
        if not dry_run:
            material.author = author
            result["updated"] += 1
        result["items"].append({
            "material_id": material.id, "filename": filename,
            "status": "repairable" if dry_run else "updated",
            "author": author,
        })
    return result


def insert_work_vault_note(s, vault_dir, filename):
    """把单篇 Work Vault 笔记写入 DB。

    使用 content_hash 作为 note_id（Work Vault 笔记没有 URL）。
    返回是否成功插入（重复则返回 False）。
    """
    vault = Path(vault_dir)
    md_path = vault / filename
    if not md_path.exists():
        return False

    text = md_path.read_text(encoding="utf-8")
    parsed = parse_work_vault_note(text, filename)

    if parsed.is_empty or not parsed.is_note:
        return False

    note_id = parsed.content_hash
    if s.query(Material).filter_by(
        platform="xiaohongshu", note_id=note_id
    ).first():
        return False

    m = Material(
        note_id=note_id,
        url="",
        title=parsed.title,
        author=extract_material_author(parsed.comments),
        author_url="",
        content=parsed.content,
        likes=0,
        collects=0,
        comments_count=parsed.comments_count,
        tags_raw=parsed.tags_raw,
        published_at=parsed.published_at or None,
        local_folder="workvault:" + filename,
    )
    s.add(m)
    s.flush()

    # 复制图片到 data/media/<note_id>/
    media_dst = config.MEDIA_DIR / note_id
    media_dst.mkdir(parents=True, exist_ok=True)
    for idx, ref in enumerate(parsed.image_refs):
        src = vault / ref
        if src.exists():
            dst = media_dst / src.name
            shutil.copy2(src, dst)
            s.add(MaterialImage(
                material_id=m.id, idx=idx,
                path=str(dst.relative_to(config.MEDIA_DIR)), type="image",
            ))

    for rank, c in enumerate(parsed.comments, 1):
        s.add(Comment(
            material_id=m.id, rank=rank, author=c["author"],
            text=c["text"], likes=c["likes"], time=c["time"],
            is_reply=False, reply_to=None,
        ))
    return True
