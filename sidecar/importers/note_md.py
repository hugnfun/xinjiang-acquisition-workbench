import re
from dataclasses import dataclass, field

@dataclass
class ParsedNote:
    title: str = ""
    metadata: dict = field(default_factory=dict)
    content: str = ""
    image_paths: list = field(default_factory=list)
    comments: list = field(default_factory=list)

_META_RE = re.compile(r"^- \*\*(?P<k>.+?)\*\*:\s?(?P<v>.*)$", re.M)
_IMG_RE = re.compile(r"^!\[.*?\]\((?P<p>images/[^)]+)\)", re.M)
_TOP_RE = re.compile(r"^- \*\*(?P<author>.+?)\*\*\s+`👍 (?P<likes>\d+) · (?P<time>[^`]+)`$")
_REPLY_RE = re.compile(r"^  ↳ \*\*(?P<author>.+?)\*\* → @(?P<reply_to>.+?)\s+`👍 (?P<likes>\d+) · (?P<time>[^`]+)`$")

def _split_sections(text: str) -> dict:
    sections = {}
    current = None
    buf = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf)
            current = line[3:].strip()
            buf = []
        else:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf)
    return sections

def _parse_comments(block: str) -> list:
    comments = []
    current = None
    for line in block.splitlines():
        if not line.strip():
            continue
        m = _TOP_RE.match(line)
        if m:
            current = {
                "author": m.group("author"),
                "likes": int(m.group("likes")),
                "time": m.group("time"),
                "is_reply": False,
                "reply_to": "",
                "text": "",
            }
            comments.append(current)
            continue
        m = _REPLY_RE.match(line)
        if m:
            current = {
                "author": m.group("author"),
                "likes": int(m.group("likes")),
                "time": m.group("time"),
                "is_reply": True,
                "reply_to": m.group("reply_to"),
                "text": "",
            }
            comments.append(current)
            continue
        if current is not None and line.startswith("  "):
            txt = line[2:].strip()
            # 跳过 "回复 X : " 前缀
            txt = re.sub(r"^回复 [^:]+ :\s*", "", txt)
            if current["text"]:
                current["text"] += " " + txt
            else:
                current["text"] = txt
    return comments

def parse_note_md(text: str) -> ParsedNote:
    sections = _split_sections(text)
    # title = 第一行 # xxx
    title = ""
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    metadata = {}
    meta_block = sections.get("元数据", "")
    for m in _META_RE.finditer(meta_block):
        metadata[m.group("k")] = m.group("v").strip()

    content = sections.get("正文", "")
    # 去掉首尾空行，保留段落间空行（strip 处理首尾，splitlines 保留内部空行）
    content = "\n".join(content.strip().splitlines())

    image_paths = _IMG_RE.findall(sections.get("图片", ""))

    # 评论 section 名形如 "评论（N 条）"，模糊匹配
    comments = []
    for k, v in sections.items():
        if k.startswith("评论"):
            comments = _parse_comments(v)
            break

    return ParsedNote(title=title, metadata=metadata, content=content,
                      image_paths=image_paths, comments=comments)
