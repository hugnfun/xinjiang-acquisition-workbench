# 新疆定制游获客工作台 · 模块 A · v0.1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个可启动的 Tauri 桌面应用，能导入已抓取的 30 篇小红书素材、用 Claude 批量打标、在 UI 上确认/改写标签、查看任务状态。

**Architecture:** Tauri (Rust) shell 内嵌 React 前端 + Python FastAPI sidecar（localhost RPC）。Sidecar 持有 SQLite + opencli runner + Claude client。前端通过 HTTP 调 sidecar。

**Tech Stack:** Tauri v2 · React 18 + Vite + TypeScript · Python 3.13 + FastAPI + SQLAlchemy 2.0 + alembic · SQLite · Anthropic SDK (claude-sonnet-4-6, prompt caching) · pytest

## Global Constraints

- **Python ≥ 3.13**（本机 3.13.5）
- **Node ≥ 24**（本机 24.12.0）
- **Rust stable**（本机未装，Task 0 安装）
- **opencli 二进制**在 PATH：`~/.npm-global/bin/opencli`（已装 v1.8.4）
- **导入源目录**：`/Users/aicer/Documents/Project/小红书-新疆旅游/`（含 30 个 `NN_标题/` 文件夹，每个有 `note.md` + `images/`，根目录有 `_manifest.json`）
- **项目根**：`/Users/aicer/Documents/Project/xinjiang-acquisition-workbench/`（git 已初始化，spec 已提交）
- **数据目录**：项目根下 `data/`（不入 git，已加 .gitignore）
- **Claude 模型**：`claude-sonnet-4-6`；API key 从环境变量 `ANTHROPIC_API_KEY` 读取
- **标签置信度阈值**：`0.6`（低于此值标记待 review）
- **所有 Python 代码用 SQLAlchemy 2.0 风格**（Mapped / mapped_column）
- **命名**：Python snake_case，TS camelCase；DB 表 snake_case
- **每个 Task 末尾必须 commit**

---

## File Structure

```
xinjiang-acquisition-workbench/
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs
│   └── src/main.rs              # spawn sidecar, 注入端口到前端
├── src/                         # React 前端
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/client.ts            # sidecar RPC 客户端
│   ├── types/models.ts          # 与 sidecar 对齐的 TS 类型
│   ├── routes/Materials.tsx
│   └── routes/Jobs.tsx
├── sidecar/
│   ├── pyproject.toml
│   ├── app.py                   # FastAPI entry, --port 参数
│   ├── config.py                # 路径/配置
│   ├── db/
│   │   ├── models.py            # SQLAlchemy v0.1 表
│   │   ├── session.py           # engine + sessionmaker
│   │   └── migrations/          # alembic
│   ├── importers/
│   │   └── note_md.py           # note.md 解析器
│   ├── opencli/
│   │   └── runner.py            # opencli subprocess 封装
│   ├── llm/
│   │   ├── client.py            # Claude client + prompt caching
│   │   └── prompts/labeling.py  # 打标 prompt + tool schema
│   ├── jobs/
│   │   ├── queue.py             # 进程内 async job 调度
│   │   └── label.py             # Flow A 批量打标 job
│   └── api/
│       ├── materials.py
│       ├── tags.py
│       └── jobs.py
├── scripts/
│   ├── import_from_folder.py    # 导入 30 篇
│   └── seed_taxonomy.py         # 初始化 6 类标签
├── tests/
│   ├── conftest.py
│   ├── test_note_md.py
│   ├── test_runner.py
│   ├── test_import.py
│   ├── test_models.py
│   ├── test_label_job.py
│   └── fixtures/                # 测试用 note.md 样本
└── data/                        # 不入 git
```

---

## Task 0: 安装 Rust 工具链

**Files:** 无（环境准备）

- [ ] **Step 1: 安装 rustup**

Run: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y`
Expected: 安装完成，提示 source 环境变量

- [ ] **Step 2: 加载环境变量并验证**

Run: `source "$HOME/.cargo/env" && cargo --version && rustc --version`
Expected: 打印 cargo 和 rustc 版本号（stable）

- [ ] **Step 3: 持久化 PATH**

把 `source "$HOME/.cargo/env"` 加到 `~/.zshrc` 末尾（若已存在则跳过）：

Run: `grep -q '.cargo/env' ~/.zshrc || echo 'source "$HOME/.cargo/env"' >> ~/.zshrc`
Expected: 无输出（已写入或已存在）

---

## Task 1: Tauri + React 项目骨架

**Files:**
- Create: `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`, `src/App.tsx`
- Create: `src-tauri/Cargo.toml`, `src-tauri/tauri.conf.json`, `src-tauri/build.rs`, `src-tauri/src/main.rs`

**Interfaces:**
- Produces: 可运行的 `npm run tauri dev`，浏览器窗口显示 "Hello workbench"

- [ ] **Step 1: 用 create-tauri-app 脚手架**

Run（在项目根）:
```bash
cd ~/Documents/Project/xinjiang-acquisition-workbench
npm create tauri-app@latest . -- --template react-ts --manager npm --yes
```
Expected: 生成 package.json / src / src-tauri 等文件。若提示目录非空选继续。

- [ ] **Step 2: 验证脚手架能跑**

Run: `npm install && npm run tauri dev`
Expected: 弹出窗口显示 Tauri+React 欢迎页。Ctrl+C 退出。

- [ ] **Step 3: 替换 App.tsx 为最小骨架**

`src/App.tsx`:
```tsx
function App() {
  return (
    <div style={{ fontFamily: 'system-ui', padding: 24 }}>
      <h1>新疆定制游获客工作台</h1>
      <p>模块 A · 素材库 + 问题池管家</p>
    </div>
  );
}
export default App;
```

- [ ] **Step 4: 验证改动能显示**

Run: `npm run tauri dev`
Expected: 窗口显示 "新疆定制游获客工作台"。Ctrl+C 退出。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: tauri+react 骨架"
```

---

## Task 2: Python sidecar 骨架 + 健康检查

**Files:**
- Create: `sidecar/pyproject.toml`, `sidecar/app.py`, `sidecar/config.py`
- Create: `tests/conftest.py`, `tests/test_app.py`

**Interfaces:**
- Produces: `sidecar.app:create_app()` 返回 FastAPI 实例；`GET /health` 返回 `{"ok": true}`；启动时读 `--port` 参数，stdout 打印 `{"port": N}`

- [ ] **Step 1: 写 pyproject.toml**

`sidecar/pyproject.toml`:
```toml
[project]
name = "workbench-sidecar"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "anthropic>=0.40",
    "pydantic>=2.9",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.24"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
```

- [ ] **Step 2: 写 config.py**

`sidecar/config.py`:
```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "data.db"
MEDIA_DIR = DATA_DIR / "media"
LOG_DIR = DATA_DIR / "logs"

def ensure_dirs():
    for d in (DATA_DIR, MEDIA_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 3: 写失败测试 test_app.py**

`tests/test_app.py`:
```python
from fastapi.testclient import TestClient
from sidecar.app import create_app

def test_health():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
```

- [ ] **Step 4: 运行测试确认失败**

Run: `cd sidecar && python -m pip install -e ".[dev]" && cd .. && python -m pytest tests/test_app.py -v`
Expected: FAIL（`sidecar.app` 不存在）

- [ ] **Step 5: 写 app.py**

`sidecar/app.py`:
```python
import argparse
import json
import sys
from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="workbench-sidecar")
    @app.get("/health")
    def health():
        return {"ok": True}
    return app

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    # 告诉 Tauri 端口
    print(json.dumps({"port": args.port}), flush=True)
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")

if __name__ == "__main__":
    main()
```

`tests/conftest.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: python sidecar 骨架 + 健康检查"
```

---

## Task 3: 数据库模型 + 迁移

**Files:**
- Create: `sidecar/db/models.py`, `sidecar/db/session.py`
- Create: `tests/test_models.py`
- Create: `sidecar/db/migrations/` (alembic init)

**Interfaces:**
- Produces: 9 张表的 SQLAlchemy 模型；`get_engine()` / `get_session()`；`init_db()` 建表

- [ ] **Step 1: 写 session.py**

`sidecar/db/session.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sidecar.config import DB_PATH, ensure_dirs

def get_engine():
    ensure_dirs()
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)

def get_session() -> Session:
    return sessionmaker(bind=get_engine())()

def init_db():
    from sidecar.db import models  # noqa: F401
    from sqlalchemy.orm import DeclarativeBase
    # models.Base.create_all 通过下方调用
    models.Base.metadata.create_all(get_engine())
```

- [ ] **Step 2: 写 models.py**

`sidecar/db/models.py`:
```python
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Material(Base):
    __tablename__ = "material"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), default="xiaohongshu")
    note_id: Mapped[str] = mapped_column(String(64), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(128))
    author_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    likes: Mapped[int] = mapped_column(Integer, default=0)
    collects: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    tags_raw: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    local_folder: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list["MaterialImage"]] = relationship(back_populates="material", cascade="all,delete")
    tags: Mapped[list["MaterialTag"]] = relationship(back_populates="material", cascade="all,delete")

class MaterialImage(Base):
    __tablename__ = "material_image"
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("material.id"))
    idx: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(16), default="image")
    material: Mapped["Material"] = relationship(back_populates="images")

class Comment(Base):
    __tablename__ = "comment"
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("material.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    author: Mapped[str] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    likes: Mapped[int] = mapped_column(Integer, default=0)
    time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_to: Mapped[str | None] = mapped_column(String(128), nullable=True)

class TagDimension(Base):
    __tablename__ = "tag_dimension"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    values: Mapped[list["TagValue"]] = relationship(back_populates="dimension", cascade="all,delete")

class TagValue(Base):
    __tablename__ = "tag_value"
    id: Mapped[int] = mapped_column(primary_key=True)
    dimension_id: Mapped[int] = mapped_column(ForeignKey("tag_dimension.id"))
    value: Mapped[str] = mapped_column(String(64))
    alias: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    dimension: Mapped["TagDimension"] = relationship(back_populates="values")
    material_tags: Mapped[list["MaterialTag"]] = relationship(back_populates="tag_value")

class MaterialTag(Base):
    __tablename__ = "material_tag"
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("material.id"))
    tag_value_id: Mapped[int] = mapped_column(ForeignKey("tag_value.id"))
    source: Mapped[str] = mapped_column(String(16), default="ai")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confirmed_by_human: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    material: Mapped["Material"] = relationship(back_populates="tags")
    tag_value: Mapped["TagValue"] = relationship(back_populates="material_tags")

class TagSuggestion(Base):
    __tablename__ = "tag_suggestion"
    id: Mapped[int] = mapped_column(primary_key=True)
    dimension_name: Mapped[str] = mapped_column(String(64))
    proposed_value: Mapped[str] = mapped_column(String(64))
    material_id: Mapped[int | None] = mapped_column(ForeignKey("material.id"), nullable=True)
    sample_context: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ScrapeJob(Base):
    __tablename__ = "scrape_job"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class JobLog(Base):
    __tablename__ = "job_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("scrape_job.id"), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 3: 写失败测试 test_models.py**

`tests/test_models.py`:
```python
from sidecar.db.session import init_db, get_session, get_engine
from sidecar.db.models import Material, TagDimension, TagValue

def test_create_material(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    init_db()
    s = get_session()
    m = Material(note_id="abc", url="http://x", title="t", author="a", likes=10)
    s.add(m); s.commit()
    assert m.id is not None
    assert s.query(Material).count() == 1

def test_tag_dimension_value_relationship(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    init_db()
    s = get_session()
    d = TagDimension(name="content_type", description="内容类型")
    s.add(d); s.commit()
    s.add(TagValue(dimension_id=d.id, value="风景震撼", alias=[])); s.commit()
    assert len(d.values) == 1
    assert d.values[0].value == "风景震撼"
```

- [ ] **Step 4: 运行测试确认失败**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL（模块/表缺失）

- [ ] **Step 5: 修复 session.py 的 monkeypatch 支持**

`sidecar/db/session.py` 修正（让 DB_PATH 读 config 但可被 monkeypatch）:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sidecar import config

def get_engine():
    config.ensure_dirs()
    return create_engine(f"sqlite:///{config.DB_PATH}", echo=False)

def get_session() -> Session:
    return sessionmaker(bind=get_engine())()

def init_db():
    from sidecar.db import models  # noqa: F401
    models.Base.metadata.create_all(get_engine())
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 7: 初始化 alembic（留作后续迁移用）**

Run: `cd sidecar && python -m alembic init db/migrations && cd ..`
Expected: 生成 `sidecar/db/migrations/`。在 `sidecar/db/migrations/env.py` 顶部加：
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from sidecar.db.models import Base
target_metadata = Base.metadata
```
（替换 env.py 里原有的 `target_metadata = None`）

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: 数据库模型 (9 表) + alembic"
```

---

## Task 4: note.md 解析器

**Files:**
- Create: `sidecar/importers/note_md.py`
- Create: `tests/test_note_md.py`, `tests/fixtures/sample_note.md`

**Interfaces:**
- Produces: `parse_note_md(text: str) -> ParsedNote`，含 title/metadata/content/image_paths/comments

- [ ] **Step 1: 写测试夹具 sample_note.md**

`tests/fixtures/sample_note.md`（精简但覆盖所有结构）:
```markdown
# 测试标题

## 元数据
- **作者**: 测试作者
- **发布时间**: 2025-10-09
- **点赞**: 1.4万
- **收藏**: 2616
- **评论数**: 721
- **标签**: #赛里木湖, #无滤镜
- **原文链接**: https://www.xiaohongshu.com/search_result/abc?xsec_token=tok&xsec_source=

## 正文

这是正文内容。#赛里木湖

## 图片

![abc_1.jpg](images/abc_1.jpg)
![abc_2.jpg](images/abc_2.jpg)

## 评论（2 条）

- **张三**  `👍 5 · 2025-10-12湖北`
  一个人去有风险吗

  ↳ **测试作者** → @张三  `👍 8 · 2025-10-12江苏`
  自己玩没事
```

- [ ] **Step 2: 写失败测试 test_note_md.py**

`tests/test_note_md.py`:
```python
from pathlib import Path
from sidecar.importers.note_md import parse_note_md, ParsedNote

FIXTURE = Path(__file__).parent / "fixtures" / "sample_note.md"

def test_parse_title_and_metadata():
    n = parse_note_md(FIXTURE.read_text(encoding="utf-8"))
    assert n.title == "测试标题"
    assert n.metadata["作者"] == "测试作者"
    assert n.metadata["点赞"] == "1.4万"
    assert n.metadata["评论数"] == "721"
    assert n.metadata["标签"] == "#赛里木湖, #无滤镜"

def test_parse_content():
    n = parse_note_md(FIXTURE.read_text(encoding="utf-8"))
    assert "这是正文内容" in n.content

def test_parse_images():
    n = parse_note_md(FIXTURE.read_text(encoding="utf-8"))
    assert n.image_paths == ["images/abc_1.jpg", "images/abc_2.jpg"]

def test_parse_comments():
    n = parse_note_md(FIXTURE.read_text(encoding="utf-8"))
    assert len(n.comments) == 2
    top = n.comments[0]
    assert top["author"] == "张三"
    assert top["likes"] == 5
    assert top["time"] == "2025-10-12湖北"
    assert top["is_reply"] is False
    assert "一个人去有风险吗" in top["text"]
    reply = n.comments[1]
    assert reply["is_reply"] is True
    assert reply["reply_to"] == "张三"
    assert reply["author"] == "测试作者"
    assert reply["likes"] == 8
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/test_note_md.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 4: 写 note_md.py**

`sidecar/importers/note_md.py`:
```python
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

    content = sections.get("正文", "").strip()
    # 去掉首尾空行
    content = "\n".join(l for l in content.splitlines() if l.strip())

    image_paths = _IMG_RE.findall(sections.get("图片", ""))

    # 评论 section 名形如 "评论（N 条）"，模糊匹配
    comments = []
    for k, v in sections.items():
        if k.startswith("评论"):
            comments = _parse_comments(v)
            break

    return ParsedNote(title=title, metadata=metadata, content=content,
                      image_paths=image_paths, comments=comments)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_note_md.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: note.md 解析器"
```

---

## Task 5: import_from_folder.py 导入脚本

**Files:**
- Create: `scripts/import_from_folder.py`
- Create: `tests/test_import.py`

**Interfaces:**
- Consumes: `parse_note_md` (Task 4), `init_db`/`get_session`/models (Task 3)
- Produces: `import_folder(source_dir, db_path=None)` 把 30 个文件夹导入 DB

- [ ] **Step 1: 写失败测试 test_import.py**

`tests/test_import.py`:
```python
from pathlib import Path
import scripts.import_from_folder as imp

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "import_root"

def test_import_folder(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    count = imp.import_folder(FIXTURE_ROOT)
    assert count == 1
    from sidecar.db.session import get_session
    from sidecar.db.models import Material, MaterialImage, Comment
    s = get_session()
    mats = s.query(Material).all()
    assert len(mats) == 1
    assert mats[0].title == "测试标题"
    assert mats[0].likes == 14000  # 1.4万 -> 14000
    assert len(mats[0].images) == 2
    assert s.query(Comment).count() == 2
```

- [ ] **Step 2: 准备测试 fixtures/import_root**

Run:
```bash
mkdir -p tests/fixtures/import_root/01_测试/images
cat > tests/fixtures/import_root/_manifest.json <<'EOF'
{"items":[{"rank":1,"title":"测试标题","author":"测试作者","likes_raw":"1.4万","likes_num":14000,"published_at":"2025-10-09","url":"https://www.xiaohongshu.com/search_result/abc?xsec_token=tok&xsec_source=","folder":"01_测试"}]}
EOF
cp tests/fixtures/sample_note.md tests/fixtures/import_root/01_测试/note.md
echo "fake" > tests/fixtures/import_root/01_测试/images/abc_1.jpg
echo "fake" > tests/fixtures/import_root/01_测试/images/abc_2.jpg
```
Expected: 无输出

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/test_import.py -v`
Expected: FAIL（脚本不存在）

- [ ] **Step 4: 写 import_from_folder.py**

`scripts/import_from_folder.py`:
```python
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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_import.py -v`
Expected: PASS

- [ ] **Step 6: 真实导入 30 篇**

Run: `python scripts/import_from_folder.py`
Expected: 打印 "导入 30 篇素材"

- [ ] **Step 7: 验证 DB 内容**

Run:
```bash
sqlite3 data/data.db "SELECT count(*) FROM material; SELECT count(*) FROM comment; SELECT count(*) FROM material_image;"
```
Expected: 三行数字（30、若干评论、若干图片）

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: import_from_folder 脚本 + 导入 30 篇"
```

---

## Task 6: seed_taxonomy.py 初始化标签维度

**Files:**
- Create: `scripts/seed_taxonomy.py`
- Create: `tests/test_seed.py`

**Interfaces:**
- Produces: `seed_taxonomy()` 建 `content_type` 维度 + 6 个值（风景震撼/避坑攻略/价格透明/行程方案/小众秘境/情绪价值）；幂等

- [ ] **Step 1: 写失败测试 test_seed.py**

`tests/test_seed.py`:
```python
import scripts.seed_taxonomy as seed

def test_seed_creates_content_type(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    seed.seed_taxonomy()
    seed.seed_taxonomy()  # 幂等
    from sidecar.db.session import get_session
    from sidecar.db.models import TagDimension, TagValue
    s = get_session()
    d = s.query(TagDimension).filter_by(name="content_type").one()
    assert len(d.values) == 6
    assert d.values[0].value == "风景震撼"

def test_seed_other_dimensions(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    seed.seed_taxonomy()
    from sidecar.db.session import get_session
    from sidecar.db.models import TagDimension
    s = get_session()
    names = {d.name for d in s.query(TagDimension).all()}
    assert {"content_type", "season", "audience", "route", "price", "emotion"} <= names
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_seed.py -v`
Expected: FAIL

- [ ] **Step 3: 写 seed_taxonomy.py**

`scripts/seed_taxonomy.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sidecar.db.session import init_db, get_session
from sidecar.db.models import TagDimension, TagValue

TAXONOMY = {
    "content_type": ("内容类型", ["风景震撼", "避坑攻略", "价格透明", "行程方案", "小众秘境", "情绪价值"]),
    "season": ("出行季节", ["春", "夏", "秋", "冬", "不限"]),
    "audience": ("目标受众", ["亲子", "情侣", "闺蜜", "独行", "中年", "摄影爱好者", "不限"]),
    "route": ("路线区域", ["北疆", "南疆", "伊犁", "喀纳斯", "独库公路", "赛里木湖", "其他"]),
    "price": ("价格区间", ["低价", "中端", "高端", "未提及"]),
    "emotion": ("情绪类型", ["震撼", "治愈", "避坑警示", "向往", "吐槽", "其他"]),
}

def seed_taxonomy():
    init_db()
    s = get_session()
    for name, (desc, values) in TAXONOMY.items():
        d = s.query(TagDimension).filter_by(name=name).first()
        if d is None:
            d = TagDimension(name=name, description=desc)
            s.add(d); s.flush()
        existing = {v.value for v in d.values}
        for v in values:
            if v not in existing:
                s.add(TagValue(dimension_id=d.id, value=v, alias=[]))
    s.commit()

if __name__ == "__main__":
    seed_taxonomy()
    print("标签体系初始化完成")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_seed.py -v`
Expected: PASS

- [ ] **Step 5: 真实初始化**

Run: `python scripts/seed_taxonomy.py`
Expected: "标签体系初始化完成"

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: seed_taxonomy 初始化 6 维度标签"
```

---

## Task 7: FastAPI materials + tags + jobs 路由

**Files:**
- Create: `sidecar/api/materials.py`, `sidecar/api/tags.py`, `sidecar/api/jobs.py`
- Modify: `sidecar/app.py`（挂载路由）
- Create: `tests/test_api.py`

**Interfaces:**
- Produces: `GET /materials`（分页+筛选）、`GET /materials/{id}`、`GET /materials/{id}/image?path=`、`POST /materials/{id}/tags`（确认/拒绝）、`GET /tags`、`GET /tags/suggestions`、`POST /tags/suggestions/{id}`、`GET /jobs`、`GET /jobs/{id}`、`POST /jobs/label`（触发打标任务）

- [ ] **Step 1: 写失败测试 test_api.py**

`tests/test_api.py`:
```python
import import_from_folder  # noqa: placeholder; see below
```
实际测试文件 `tests/test_api.py`:
```python
from fastapi.testclient import TestClient
import scripts.import_from_folder as imp
import scripts.seed_taxonomy as seed
from sidecar.app import create_app

def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")
    return TestClient(create_app())

from pathlib import Path

def test_list_materials(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.get("/materials")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "测试标题"

def test_get_material_detail(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    mid = client.get("/materials").json()["items"][0]["id"]
    r = client.get(f"/materials/{mid}")
    assert r.status_code == 200
    assert "content" in r.json()
    assert len(r.json()["images"]) == 2

def test_list_tags(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.get("/tags")
    assert r.status_code == 200
    names = {d["name"] for d in r.json()}
    assert "content_type" in names
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_api.py -v`
Expected: FAIL（路由不存在）

- [ ] **Step 3: 写 materials.py**

`sidecar/api/materials.py`:
```python
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from fastapi.responses import FileResponse
from sidecar.db.session import get_session
from sidecar.db.models import Material, MaterialTag, TagValue, TagDimension
from sidecar import config

router = APIRouter()

@router.get("/materials")
def list_materials(limit: int = 50, offset: int = 0, order: str = "likes"):
    s = get_session()
    q = s.query(Material)
    col = Material.likes if order == "likes" else Material.fetched_at
    q = q.order_by(col.desc())
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [_material_summary(s, m) for m in items],
    }

def _material_summary(s, m):
    tags = s.query(MaterialTag).filter_by(material_id=m.id).all()
    return {
        "id": m.id, "title": m.title, "author": m.author,
        "likes": m.likes, "collects": m.collects, "comments_count": m.comments_count,
        "published_at": m.published_at, "tags_raw": m.tags_raw,
        "image_count": len(m.images),
        "tags": [_tag_view(s, t) for t in tags],
    }

def _tag_view(s, mt):
    tv = s.query(TagValue).get(mt.tag_value_id)
    dim = s.query(TagDimension).get(tv.dimension_id) if tv else None
    return {
        "tag_value_id": mt.tag_value_id,
        "dimension": dim.name if dim else None,
        "value": tv.value if tv else None,
        "source": mt.source,
        "confidence": mt.confidence,
        "confirmed_by_human": mt.confirmed_by_human,
    }

@router.get("/materials/{mid}")
def get_material(mid: int):
    s = get_session()
    m = s.query(Material).get(mid)
    if not m:
        raise HTTPException(404)
    summary = _material_summary(s, m)
    summary.update({
        "content": m.content,
        "url": m.url,
        "local_folder": m.local_folder,
        "images": [{"idx": i.idx, "path": i.path, "type": i.type} for i in m.images],
    })
    return summary

@router.get("/materials/{mid}/image")
def get_image(mid: int, path: str):
    full = config.MEDIA_DIR / path
    if not full.exists() or not str(full).startswith(str(config.MEDIA_DIR)):
        raise HTTPException(404)
    return FileResponse(full)
```

- [ ] **Step 4: 写 tags.py**

`sidecar/api/tags.py`:
```python
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sidecar.db.session import get_session
from sidecar.db.models import TagDimension, TagValue, MaterialTag, TagSuggestion

router = APIRouter()

@router.get("/tags")
def list_tags():
    s = get_session()
    out = []
    for d in s.query(TagDimension).all():
        out.append({
            "id": d.id, "name": d.name, "description": d.description,
            "values": [{"id": v.id, "value": v.value, "alias": v.alias, "status": v.status}
                       for v in d.values if v.status == "active"],
        })
    return out

class ConfirmTagIn(BaseModel):
    tag_value_id: int
    action: str  # 'confirm' | 'reject'

@router.post("/materials/{mid}/tags")
def manage_material_tag(mid: int, body: ConfirmTagIn):
    s = get_session()
    mt = s.query(MaterialTag).filter_by(material_id=mid, tag_value_id=body.tag_value_id).first()
    if body.action == "confirm":
        if mt:
            mt.confirmed_by_human = True
            mt.confirmed_at = datetime.utcnow()
        s.commit()
        return {"ok": True}
    elif body.action == "reject":
        if mt:
            s.delete(mt)
        s.commit()
        return {"ok": True}
    raise HTTPException(400, "unknown action")

@router.get("/tags/suggestions")
def list_suggestions():
    s = get_session()
    return [{
        "id": sg.id, "dimension_name": sg.dimension_name,
        "proposed_value": sg.proposed_value, "status": sg.status,
        "sample_context": sg.sample_context, "material_id": sg.material_id,
    } for sg in s.query(TagSuggestion).filter_by(status="pending").all()]

class SuggestionActionIn(BaseModel):
    action: str           # 'accept' | 'reject' | 'merge'
    merge_into_value_id: int | None = None

@router.post("/tags/suggestions/{sid}")
def act_suggestion(sid: int, body: SuggestionActionIn):
    s = get_session()
    sg = s.query(TagSuggestion).get(sid)
    if not sg:
        raise HTTPException(404)
    if body.action == "accept":
        d = s.query(TagDimension).filter_by(name=sg.dimension_name).first()
        if d:
            s.add(TagValue(dimension_id=d.id, value=sg.proposed_value, alias=[]))
        sg.status = "accepted"
    elif body.action == "merge" and body.merge_into_value_id:
        tv = s.query(TagValue).get(body.merge_into_value_id)
        if tv:
            tv.alias.append(sg.proposed_value)
        sg.status = "merged"
    elif body.action == "reject":
        sg.status = "rejected"
    s.commit()
    return {"ok": True}
```

- [ ] **Step 5: 写 jobs.py（占位，打标 job 在 Task 9 接入）**

`sidecar/api/jobs.py`:
```python
from fastapi import APIRouter
from sidecar.db.session import get_session
from sidecar.db.models import ScrapeJob, JobLog

router = APIRouter()

@router.get("/jobs")
def list_jobs(limit: int = 50):
    s = get_session()
    jobs = s.query(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(limit).all()
    return [{
        "id": j.id, "type": j.type, "status": j.status,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        "error": j.error,
    } for j in jobs]

@router.get("/jobs/{jid}")
def get_job(jid: int):
    s = get_session()
    j = s.query(ScrapeJob).get(jid)
    if not j:
        return {"error": "not found"}
    logs = s.query(JobLog).filter_by(job_id=jid).order_by(JobLog.created_at).all()
    return {
        "id": j.id, "type": j.type, "status": j.status,
        "params": j.params, "result_summary": j.result_summary, "error": j.error,
        "logs": [{"level": l.level, "message": l.message,
                  "created_at": l.created_at.isoformat() if l.created_at else None}
                 for l in logs],
    }
```

- [ ] **Step 6: 在 app.py 挂载路由**

修改 `sidecar/app.py` 的 `create_app`，在 health 路由后加：
```python
    from sidecar.api import materials, tags, jobs
    app.include_router(materials.router)
    app.include_router(tags.router)
    app.include_router(jobs.router)
```

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: materials/tags/jobs API 路由"
```

---

## Task 8: opencli runner 封装

**Files:**
- Create: `sidecar/opencli/runner.py`
- Create: `tests/test_runner.py`

**Interfaces:**
- Produces: `run_opencli(args: list[str]) -> list|dict`（subprocess 调 opencli，解析 JSON）；`search(query, limit)`/`note(url)`/`comments(url, limit, with_replies)`/`download(url, output)`

- [ ] **Step 1: 写失败测试 test_runner.py（用 monkeypatch 不真调 opencli）**

`tests/test_runner.py`:
```python
import json
from sidecar.opencli import runner

def test_parse_json_output_extracts_array():
    raw = 'some banner\n[{"a":1}]\nUpdate available'
    assert runner._extract_json(raw) == [{"a": 1}]

def test_parse_json_output_extracts_object():
    raw = '{"ok": true}'
    assert runner._extract_json(raw) == {"ok": True}

def test_run_opencli_calls_subprocess(monkeypatch):
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        class R:
            returncode = 0
            stdout = '[{"rank":1}]'
            stderr = ""
        return R()
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    out = runner.run_opencli(["xhs", "search", "x", "-f", "json"])
    assert out == [{"rank": 1}]
    assert captured["cmd"][0].endswith("opencli")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_runner.py -v`
Expected: FAIL

- [ ] **Step 3: 写 runner.py**

`sidecar/opencli/runner.py`:
```python
import json
import re
import shutil
import subprocess
from pathlib import Path

OPENCLI_BIN = shutil.which("opencli") or "opencli"

def _extract_json(text: str):
    text = text.strip()
    m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
    if not m:
        raise ValueError(f"no JSON in opencli output: {text[:200]}")
    return json.loads(m.group(1))

def run_opencli(args: list[str], timeout: int = 180):
    cmd = [OPENCLI_BIN] + args
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"opencli failed: {' '.join(args)}\n{res.stderr[:500]}")
    return _extract_json(res.stdout)

def search(query: str, limit: int = 20):
    return run_opencli(["xiaohongshu", "search", query, "--limit", str(limit), "-f", "json"])

def note(url: str):
    return run_opencli(["xiaohongshu", "note", url, "-f", "json"], timeout=120)

def comments(url: str, limit: int = 50, with_replies: bool = True):
    args = ["xiaohongshu", "comments", url, "--limit", str(limit), "-f", "json"]
    if with_replies:
        args.append("--with-replies")
    return run_opencli(args, timeout=180)

def download(url: str, output: str):
    return run_opencli(["xiaohongshu", "download", url, "--output", output, "-f", "json"], timeout=300)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: opencli runner 封装"
```

---

## Task 9: LLM client + 打标 prompt

**Files:**
- Create: `sidecar/llm/client.py`, `sidecar/llm/prompts/labeling.py`
- Create: `tests/test_label_job.py`

**Interfaces:**
- Produces: `label_material(material, taxonomy) -> list[LabelResult]`，每条 `{dimension, value, confidence}`；用 tool use 强制结构化输出；prompt caching 缓存 taxonomy+system

- [ ] **Step 1: 写失败测试 test_label_job.py（mock anthropic client）**

`tests/test_label_job.py`:
```python
from sidecar.llm import labeling as L

def test_label_material_parses_tool_use(monkeypatch):
    fake_tool_input = {
        "labels": [
            {"dimension": "content_type", "value": "风景震撼", "confidence": 0.9},
            {"dimension": "season", "value": "秋", "confidence": 0.7},
        ]
    }
    block = type("B", (), {"type": "tool_use", "input": fake_tool_input})()
    class FakeResp:
        content = [block]
    class FakeClient:
        def messages(self):
            return self
        def create(self, **kw):
            return FakeResp()
    monkeypatch.setattr(L, "_get_client", lambda: FakeClient())
    result = L.label_material(
        title="赛里木湖", content="湖很蓝", image_paths=[],
        taxonomy=[{"name":"content_type","values":["风景震撼"]}],
    )
    assert len(result) == 2
    assert result[0]["value"] == "风景震撼"
    assert result[0]["confidence"] == 0.9
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_label_job.py -v`
Expected: FAIL

- [ ] **Step 3: 写 labeling.py（含 client + prompt + tool schema）**

`sidecar/llm/prompts/__init__.py`: 空文件
`sidecar/llm/labeling.py`:
```python
import os
import base64
from pathlib import Path
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

def _get_client():
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

LABEL_TOOL = {
    "name": "record_labels",
    "description": "记录对一篇小红书笔记的标签判定结果",
    "input_schema": {
        "type": "object",
        "properties": {
            "labels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "dimension": {"type": "string"},
                        "value": {"type": "string"},
                        "confidence": {"type": "number"},
                        "out_of_taxonomy": {"type": "boolean"},
                    },
                    "required": ["dimension", "value", "confidence", "out_of_taxonomy"],
                },
            }
        },
        "required": ["labels"],
    },
}

def _build_system(taxonomy: list) -> str:
    lines = ["你是一个小红书新疆旅游内容标注助手。", "可用标签体系如下，只能从中选值；若都不合适，标记 out_of_taxonomy=true 并给出建议值。", ""]
    for dim in taxonomy:
        vals = "、".join(dim["values"])
        lines.append(f"维度 {dim['name']}（{dim.get('description','')}）: {vals}")
    lines.append("")
    lines.append("输出规则：每篇笔记给出至少 3 个标签；confidence 0~1；置信度<0.6 的也照给。")
    return "\n".join(lines)

def _encode_image(path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode()
    ext = path.suffix.lstrip(".").lower()
    media = "jpeg" if ext in ("jpg", "jpeg") else ext
    return {"type": "image", "source": {"type": "base64", "media_type": f"image/{media}", "data": data}}

def label_material(title: str, content: str, image_paths: list[Path], taxonomy: list) -> list:
    client = _get_client()
    system = _build_system(taxonomy)
    user_content = [{"type": "text", "text": f"标题：{title}\n\n正文：{content}"}]
    for p in image_paths[:3]:  # 最多 3 张图省 token
        p = Path(p)
        if p.exists():
            user_content.append(_encode_image(p))

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        tools=[LABEL_TOOL],
        tool_choice={"type": "tool", "name": "record_labels"},
        messages=[{"role": "user", "content": user_content}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input.get("labels", [])
    return []
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_label_job.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: LLM 打标 client + prompt caching"
```

---

## Task 10: Flow A 批量打标 job

**Files:**
- Create: `sidecar/jobs/queue.py`, `sidecar/jobs/label.py`
- Modify: `sidecar/api/jobs.py`（加 `POST /jobs/label` 触发）
- Create: `tests/test_label_flow.py`

**Interfaces:**
- Consumes: `label_material` (Task 9), models (Task 3)
- Produces: `run_label_job(job_id)` 异步跑全量打标；写 `material_tag` + `tag_suggestion`

- [ ] **Step 1: 写失败测试 test_label_flow.py（mock label_material）**

`tests/test_label_flow.py`:
```python
import scripts.seed_taxonomy as seed
import scripts.import_from_folder as imp
from sidecar.jobs import label as labeljob

def test_run_label_job_writes_tags(tmp_path, monkeypatch):
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")

    def fake_label(title, content, image_paths, taxonomy):
        return [
            {"dimension": "content_type", "value": "风景震撼", "confidence": 0.9, "out_of_taxonomy": False},
            {"dimension": "content_type", "value": "绝美日出", "confidence": 0.5, "out_of_taxonomy": True},
        ]
    monkeypatch.setattr(labeljob, "label_material", fake_label)

    from sidecar.db.session import get_session
    from sidecar.db.models import ScrapeJob
    s = get_session()
    job = ScrapeJob(type="label_batch", status="queued", params={})
    s.add(job); s.commit()

    labeljob.run_label_job(job.id)

    from sidecar.db.models import MaterialTag, TagSuggestion
    s2 = get_session()
    assert s2.query(MaterialTag).count() >= 1
    assert s2.query(MaterialTag).filter_by(confirmed_by_human=False).count() >= 1
    assert s2.query(TagSuggestion).filter_by(status="pending").count() == 1
    job = s2.query(ScrapeJob).get(job.id)
    assert job.status == "done"

from pathlib import Path
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_label_flow.py -v`
Expected: FAIL

- [ ] **Step 3: 写 queue.py**

`sidecar/jobs/queue.py`:
```python
import asyncio
import threading

_queue: asyncio.Queue = None
_loop: asyncio.AbstractEventLoop = None
_thread: threading.Thread = None

def start_worker():
    global _queue, _loop, _thread
    if _thread and _thread.is_alive():
        return
    _queue = asyncio.Queue()
    _loop = asyncio.new_event_loop()

    def _run():
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()

def submit(coro):
    if _loop is None:
        start_worker()
    fut = asyncio.run_coroutine_threadsafe(coro, _loop)
    return fut
```

- [ ] **Step 4: 写 label.py**

`sidecar/jobs/label.py`:
```python
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
    try:
        for m in materials:
            image_paths = [config.MEDIA_DIR / img.path for img in m.images[:3]]
            try:
                labels = label_material(m.title, m.content, image_paths, taxonomy)
            except Exception as e:
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
                    material_id=m.id, tag_value_id=tv.id, source="ai",
                    confidence=conf, confirmed_by_human=False))
            labeled += 1
            _log(s, job_id, f"素材 {m.id} 完成 ({len(labels)} 标签)")
            s.commit()
        job.status = "done"
        job.result_summary = {"labeled": labeled, "total": len(materials)}
        _log(s, job_id, f"完成，共 {labeled} 篇")
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        _log(s, job_id, f"失败: {e}", "error")
    finally:
        job.finished_at = datetime.utcnow()
        s.commit()
```

- [ ] **Step 5: 在 jobs.py 加触发端点**

`sidecar/api/jobs.py` 末尾加：
```python
from sidecar.jobs.queue import submit
from sidecar.jobs.label import run_label_job
import asyncio

@router.post("/jobs/label")
def trigger_label():
    s = get_session()
    from sidecar.db.models import ScrapeJob
    job = ScrapeJob(type="label_batch", status="queued", params={})
    s.add(job); s.commit(); s.refresh(job)
    submit(asyncio.to_thread(run_label_job, job.id))
    return {"job_id": job.id}
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_label_flow.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: Flow A 批量打标 job + 触发端点"
```

---

## Task 11: 前端 API client + 类型

**Files:**
- Create: `src/types/models.ts`, `src/api/client.ts`

**Interfaces:**
- Produces: `api.getMaterials()` / `getMaterial(id)` / `getTags()` / `getJobs()` / `triggerLabel()` / `confirmTag()` / `getImageUrl()`

- [ ] **Step 1: 写 types/models.ts**

`src/types/models.ts`:
```typescript
export interface TagView {
  tag_value_id: number;
  dimension: string | null;
  value: string | null;
  source: string;
  confidence: number | null;
  confirmed_by_human: boolean;
}
export interface MaterialSummary {
  id: number; title: string; author: string;
  likes: number; collects: number; comments_count: number;
  published_at: string | null; tags_raw: string;
  image_count: number; tags: TagView[];
}
export interface MaterialDetail extends MaterialSummary {
  content: string; url: string; local_folder: string | null;
  images: { idx: number; path: string; type: string }[];
}
export interface TagDimensionView {
  id: number; name: string; description: string;
  values: { id: number; value: string; alias: string[]; status: string }[];
}
export interface JobView {
  id: number; type: string; status: string;
  created_at: string | null; started_at: string | null;
  finished_at: string | null; error: string | null;
}
```

- [ ] **Step 2: 写 api/client.ts**

`src/api/client.ts`:
```typescript
import type { MaterialSummary, MaterialDetail, TagDimensionView, JobView } from '../types/models';

const BASE = (import.meta as any).env.VITE_SIDECAR_PORT
  ? `http://127.0.0.1:${(import.meta as any).env.VITE_SIDECAR_PORT}`
  : 'http://127.0.0.1:8765';

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
async function post<T>(path: string, body: any): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  getMaterials: (limit = 50, offset = 0) =>
    get<{ total: number; items: MaterialSummary[] }>(`/materials?limit=${limit}&offset=${offset}`),
  getMaterial: (id: number) => get<MaterialDetail>(`/materials/${id}`),
  getTags: () => get<TagDimensionView[]>(`/tags`),
  getJobs: () => get<JobView[]>(`/jobs`),
  getJob: (id: number) => get<any>(`/jobs/${id}`),
  triggerLabel: () => post<{ job_id: number }>(`/jobs/label`, {}),
  confirmTag: (mid: number, tag_value_id: number, action: 'confirm' | 'reject') =>
    post(`/materials/${mid}/tags`, { tag_value_id, action }),
  getImageUrl: (mid: number, path: string) => `${BASE}/materials/${mid}/image?path=${encodeURIComponent(path)}`,
};
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: 前端 api client + 类型"
```

---

## Task 12: /materials 视图

**Files:**
- Create: `src/routes/Materials.tsx`
- Modify: `src/App.tsx`（加 tab 切换）

**Interfaces:**
- Consumes: `api` (Task 11)

- [ ] **Step 1: 写 Materials.tsx**

`src/routes/Materials.tsx`:
```tsx
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { MaterialSummary, MaterialDetail } from '../types/models';

export default function Materials() {
  const [list, setList] = useState<MaterialSummary[]>([]);
  const [selected, setSelected] = useState<MaterialDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getMaterials(50, 0).then(r => setList(r.items));
  }, []);

  const open = async (id: number) => {
    setLoading(true);
    const d = await api.getMaterial(id);
    setSelected(d); setLoading(false);
  };

  const onTagAction = async (tvId: number, action: 'confirm' | 'reject') => {
    if (!selected) return;
    await api.confirmTag(selected.id, tvId, action);
    const d = await api.getMaterial(selected.id);
    setSelected(d);
    const r = await api.getMaterials(50, 0);
    setList(r.items);
  };

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <div style={{ width: '40%', overflow: 'auto', borderRight: '1px solid #eee' }}>
        {list.map(m => (
          <div key={m.id} onClick={() => open(m.id)}
               style={{ padding: 12, cursor: 'pointer', borderBottom: '1px solid #f5f5f5' }}>
            <div style={{ fontWeight: 500 }}>{m.title}</div>
            <div style={{ color: '#888', fontSize: 13 }}>
              👤{m.author} 👍{m.likes} 💬{m.comments_count}
            </div>
            <div>
              {m.tags.map(t => (
                <span key={t.tag_value_id} style={{
                  fontSize: 12, margin: 2, padding: '2px 6px',
                  borderRadius: 4,
                  background: t.confirmed_by_human ? '#d4edda' : '#fff3cd',
                  opacity: t.confidence != null && t.confidence < 0.6 ? 0.6 : 1,
                }}>
                  {t.value}{t.confidence != null && t.confidence < 0.6 ? '?' : ''}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        {loading && <p>加载中...</p>}
        {selected && (
          <>
            <h2>{selected.title}</h2>
            <p style={{ color: '#666' }}>👤{selected.author} · 👍{selected.likes} · 💛{selected.collects} · 💬{selected.comments_count}</p>
            <div style={{ display: 'flex', gap: 8, overflowX: 'auto', marginBottom: 16 }}>
              {selected.images.map(img => (
                <img key={img.idx} src={api.getImageUrl(selected.id, img.path)}
                     style={{ height: 200, borderRadius: 8 }} />
              ))}
            </div>
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{selected.content}</pre>
            <h3>标签</h3>
            {selected.tags.map(t => (
              <div key={t.tag_value_id} style={{ marginBottom: 6 }}>
                <span style={{ background: '#f0f0f0', padding: '2px 8px', borderRadius: 4 }}>
                  [{t.dimension}] {t.value}
                  {t.confidence != null && ` (${t.confidence})`}
                  {t.confirmed_by_human ? ' ✓' : ''}
                </span>
                {!t.confirmed_by_human && (
                  <>
                    <button onClick={() => onTagAction(t.tag_value_id, 'confirm')}>确认</button>
                    <button onClick={() => onTagAction(t.tag_value_id, 'reject')}>拒绝</button>
                  </>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 改 App.tsx 加 tab**

`src/App.tsx`:
```tsx
import { useState } from 'react';
import Materials from './routes/Materials';
import Jobs from './routes/Jobs';

export default function App() {
  const [tab, setTab] = useState<'materials' | 'jobs'>('materials');
  return (
    <div style={{ fontFamily: 'system-ui' }}>
      <div style={{ borderBottom: '1px solid #eee', padding: '8px 16px' }}>
        <strong style={{ marginRight: 24 }}>新疆定制游获客工作台</strong>
        <button onClick={() => setTab('materials')} style={{ fontWeight: tab==='materials'?700:400 }}>素材库</button>
        <button onClick={() => setTab('jobs')} style={{ fontWeight: tab==='jobs'?700:400, marginLeft: 8 }}>任务中心</button>
      </div>
      {tab === 'materials' ? <Materials /> : <Jobs />}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: /materials 视图 + tab 框架"
```

---

## Task 13: /jobs 视图 + 触发打标

**Files:**
- Create: `src/routes/Jobs.tsx`

- [ ] **Step 1: 写 Jobs.tsx**

`src/routes/Jobs.tsx`:
```tsx
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { JobView } from '../types/models';

export default function Jobs() {
  const [jobs, setJobs] = useState<JobView[]>([]);
  const [busy, setBusy] = useState(false);

  const refresh = () => api.getJobs().then(setJobs);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  const trigger = async () => {
    setBusy(true);
    try { await api.triggerLabel(); } finally { setBusy(false); }
    setTimeout(refresh, 500);
  };

  return (
    <div style={{ padding: 16 }}>
      <h2>任务中心</h2>
      <button onClick={trigger} disabled={busy}>
        {busy ? '提交中...' : '▶ 触发批量打标（全部素材）'}
      </button>
      <table style={{ marginTop: 16, width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr><th align="left">ID</th><th align="left">类型</th><th align="left">状态</th><th align="left">创建</th><th align="left">错误</th></tr>
        </thead>
        <tbody>
          {jobs.map(j => (
            <tr key={j.id} style={{ borderBottom: '1px solid #eee' }}>
              <td>{j.id}</td>
              <td>{j.type}</td>
              <td>{j.status}</td>
              <td>{j.created_at}</td>
              <td style={{ color: 'red' }}>{j.error}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "feat: /jobs 视图 + 触发打标"
```

---

## Task 14: Tauri 集成 sidecar + 端到点冒烟

**Files:**
- Modify: `src-tauri/src/main.rs`（启动时 spawn sidecar，读端口注入前端）
- Modify: `src-tauri/tauri.conf.json`（dev 时注入 env）
- Modify: `package.json`（dev 脚本带 sidecar）

**Interfaces:**
- Produces: `npm run tauri dev` 自动起 sidecar，前端能调通 API

- [ ] **Step 1: 写 main.rs spawn sidecar 并注入端口**

`src-tauri/src/main.rs`:
```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Stdio};
use std::io::{BufRead, BufReader};
use tauri::Manager;

fn spawn_sidecar() -> u16 {
    // 找一个空闲端口给 sidecar
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    drop(listener);

    let py = std::env::var("SIDECAR_PY").unwrap_or("python3".into());
    let module = std::env::var("SIDECAR_MODULE").unwrap_or("sidecar.app".into());
    let project_root = std::env::current_dir().unwrap();

    let mut child = Command::new(py)
        .arg("-m")
        .arg(&module)
        .arg("--port").arg(port.to_string())
        .current_dir(project_root.join("sidecar").parent().unwrap())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("failed to spawn sidecar");

    // 读取第一行 stdout 拿 port（防止端口被占用变化）
    let stdout = child.stdout.take().unwrap();
    let reader = BufReader::new(stdout);
    for line in reader.lines() {
        if let Ok(l) = line {
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&l) {
                if let Some(p) = v.get("port").and_then(|x| x.as_u64()) {
                    std::mem::forget(child); // 保持 sidecar 存活
                    return p as u16;
                }
            }
        }
        break;
    }
    port
}

fn main() {
    let port = spawn_sidecar();
    tauri::Builder::default()
        .setup(move |app| {
            // 注入端口到前端环境变量（通过 window label 或全局）
            #[cfg(debug_assertions)]
            {
                let main_window = app.get_webview_window("main").unwrap();
                let _ = main_window.eval(&format!(
                    "window.__SIDECAR_PORT__ = {};", port
                ));
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![])
        .run(tauri::generate_context!())
        .expect("error while running tauri app");
}
```

`src-tauri/Cargo.toml` 的 `[dependencies]` 加：
```toml
serde_json = "1"
```

- [ ] **Step 2: 前端读注入端口**

修改 `src/api/client.ts` 顶部 BASE 改为优先读 window 注入：
```typescript
function getPort(): string {
  // Tauri 注入的端口
  const injected = (window as any).__SIDECAR_PORT__;
  if (injected) return String(injected);
  // vite env
  const env = (import.meta as any).env.VITE_SIDECAR_PORT;
  if (env) return String(env);
  return '8765';
}
const BASE = `http://127.0.0.1:${getPort()}`;
```

- [ ] **Step 3: 端到端冒烟测试**

确保 `ANTHROPIC_API_KEY` 已设。Run:
```bash
export ANTHROPIC_API_KEY="<your key>"   # 用户已配则跳过
npm run tauri dev
```
手动验证：
1. 窗口打开，素材库 tab 显示 30 条素材
2. 点一条，右侧显示正文 + 图片 + 标签（此时标签为空）
3. 切到任务中心，点「触发批量打标」
4. 等 job 状态变 done（约 1-3 分钟）
5. 切回素材库，每条素材显示 AI 推荐标签 chips
6. 点「确认」标签变绿，「拒绝」消失

Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: tauri 集成 sidecar + 端到端冒烟通过"
```

---

## 验收标准（v0.1 完成）

对照 spec §11：
1. ✅ 双击图标启动应用，无报错（Task 14 Step 3）
2. ✅ 30 篇素材在 `/materials` 可见，能筛选/排序（Task 12）
3. ✅ 触发「全量打标」后完成，每条素材至少 3 个 AI 推荐标签（Task 10 + 14）
4. ✅ 可在 UI 上确认/改写/拒绝 AI 标签（Task 7 + 12）
5. ✅ SQLite 文件可用 DB Browser 打开检查（Task 5 Step 7 验证过结构）

---

## 备注

- 标签改写（reject 后改写成别的标签）v0.1 简化为「拒绝即删除」；完整改写留 v0.2
- 图片只取前 3 张送 LLM 省 token（Task 9）
- `tag_suggestion` 收件箱 UI 留 v0.2（v0.1 API 已就绪，前端待补）
- Flow C 问题池冷启动留 v0.2 计划
