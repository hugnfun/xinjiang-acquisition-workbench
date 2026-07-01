# LLM Provider 切换 (DeepSeek + 本地 qwen-vl) 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把模块 A 打标 LLM 从 Anthropic Claude 切换为 DeepSeek（文本）+ 本地 Ollama qwen3-vl（视觉）双路串行补标，配置化、可降级。

**Architecture:** labeling.py 重写为 openai SDK 驱动：DeepSeek 文本打标（JSON mode）→ 低置信度触发 qwen-vl 看首图补标 → 合并去重。模型/base/key 全走 env。label.py 的 material_tag.source 区分 ai_text/ai_vision。DB/API/UI/Tauri 不动。

**Tech Stack:** Python 3.13 · openai SDK (≥1.50, OpenAI 兼容接口同时连 DeepSeek 与 Ollama) · DeepSeek `deepseek-v4-pro` · Ollama `qwen3-vl:8b` · pytest

## Global Constraints

- **Python ≥ 3.13**, venv `.venv`，测试 `.venv/bin/python -m pytest -v`（保持 pristine），pyproject 在项目根。
- **DeepSeek 模型 ID = `deepseek-v4-pro`**（小写连字符；旧名 deepseek-chat/reasoner 2026/07/24 下线，不用）。base `https://api.deepseek.com/v1`，key 读 env `DEEPSEEK_API_KEY`。
- **视觉模型 = `qwen3-vl:8b`**（本地 Ollama，已验证 `localhost:11434/api/tags` 返回该模型），base `http://localhost:11434/v1`，无需 key。
- 两个模型都走 **OpenAI 兼容接口**，统一用 `openai` SDK 调用。
- 文本路用 `response_format={"type":"json_object"}`（DeepSeek 支持）；视觉路**不用** response_format（Ollama 不稳），靠 prompt 约束 + `_parse_labels` 容错提取。
- 触发阈值 `VISION_TRIGGER_CONFIDENCE = 0.6`（env 可调）。
- **触发逻辑置信度专属**：只要文本标签里存在 confidence < 0.6 的，就触发视觉补标；全 ≥0.6 则跳过。（spec §3 提到的"维度缺失"条款舍弃——DeepSeek 给 ≥3 标签跨 6 维度，必然有维度"缺失"，会永远触发，违背"文本够就跳过"的初衷。这是对 spec 触发条件的精简，忠实于用户选的"① 按置信度阈值"。）
- `material_tag.source` 新值：`'ai_text'`（DeepSeek 文本）/ `'ai_vision'`（qwen-vl 视觉）。schema 不变（source 已是字符串）。
- `anthropic` 包**保留不删**（避免破坏性改动；labeling 不再调用它）。
- 每 Task 末尾 commit。

---

## File Structure

```
sidecar/
├── config.py              # Modify: 加 LLM 配置块（TEXT_*/VISION_*/阈值）
└── llm/
    └── labeling.py        # Rewrite: openai 双路 + 串行编排 + 合并去重
sidecar/jobs/
└── label.py               # Modify: material_tag.source 从 lb 读
pyproject.toml             # Modify: 加 openai>=1.50 依赖
tests/
└── test_label_job.py      # Rewrite: mock 两个 openai client，验证编排+合并
└── test_label_flow.py     # Modify: 断言 source 写入正确值
```

---

## Task 1: openai 依赖 + config LLM 配置

**Files:**
- Modify: `pyproject.toml`（dependencies 加 openai）
- Modify: `sidecar/config.py`（加 LLM 配置块）
- Test: `tests/test_config.py`（新建）

**Interfaces:**
- Produces: `sidecar.config` 新增 `TEXT_MODEL, TEXT_API_BASE, TEXT_API_KEY, VISION_MODEL, VISION_API_BASE, VISION_API_KEY, VISION_TRIGGER_CONFIDENCE, VISION_MAX_IMAGES`；`openai` 可 import。

- [ ] **Step 1: 写失败测试 tests/test_config.py**

`tests/test_config.py`:
```python
import os
import importlib
from sidecar import config

def test_text_config_defaults(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("TEXT_MODEL", raising=False)
    monkeypatch.delenv("TEXT_API_BASE", raising=False)
    importlib.reload(config)
    assert config.TEXT_MODEL == "deepseek-v4-pro"
    assert config.TEXT_API_BASE == "https://api.deepseek.com/v1"
    assert config.TEXT_API_KEY == ""

def test_text_config_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("TEXT_MODEL", "custom-model")
    importlib.reload(config)
    assert config.TEXT_API_KEY == "sk-test"
    assert config.TEXT_MODEL == "custom-model"

def test_vision_config_defaults(monkeypatch):
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    importlib.reload(config)
    assert config.VISION_MODEL == "qwen3-vl:8b"
    assert config.VISION_API_BASE == "http://localhost:11434/v1"
    assert config.VISION_API_KEY == "ollama"
    assert config.VISION_TRIGGER_CONFIDENCE == 0.6
    assert config.VISION_MAX_IMAGES == 1

def test_openai_importable():
    import openai
    assert openai.__version__
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL（`No module named 'openai'`，且 config 无 TEXT_* 属性）

- [ ] **Step 3: pyproject.toml 加 openai 依赖**

在 `pyproject.toml` 的 `[project] dependencies` 列表里加一行（紧跟现有依赖）：
```toml
    "openai>=1.50",
```

安装：
```bash
cd ~/Documents/Project/xinjiang-acquisition-workbench
.venv/bin/pip install -e ".[dev]"
```
若 pip 通过代理 SSL 失败，禁用代理重试：`env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY .venv/bin/pip install -e ".[dev]"`

- [ ] **Step 4: config.py 加 LLM 配置块**

在 `sidecar/config.py` 末尾追加（保留原有 PROJECT_ROOT/DATA_DIR 等）：
```python
import os

# ── LLM provider 配置（env 驱动，可切换） ──
# 文本模型 (DeepSeek)
TEXT_MODEL = os.environ.get("TEXT_MODEL", "deepseek-v4-pro")
TEXT_API_BASE = os.environ.get("TEXT_API_BASE", "https://api.deepseek.com/v1")
TEXT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# 视觉模型 (本地 Ollama qwen-vl)
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen3-vl:8b")
VISION_API_BASE = os.environ.get("VISION_API_BASE", "http://localhost:11434/v1")
VISION_API_KEY = os.environ.get("VISION_API_KEY", "ollama")

# 视觉补标触发阈值：文本标签 confidence < 此值 → 看图补
VISION_TRIGGER_CONFIDENCE = float(os.environ.get("VISION_TRIGGER_CONFIDENCE", "0.6"))
VISION_MAX_IMAGES = int(os.environ.get("VISION_MAX_IMAGES", "1"))
```

注意：`import os` 加在文件顶部（若 config.py 顶部已有别的 import，合并；当前 config.py 顶部是 `from pathlib import Path`，把 `import os` 放在它之前或之后均可）。

- [ ] **Step 5: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS（4/4）

- [ ] **Step 6: 运行全量套件确认无回归**

Run: `.venv/bin/python -m pytest -v`
Expected: 全绿（旧 test_label_job.py 仍用 anthropic _get_client mock，未动 labeling.py，应仍通过）

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml sidecar/config.py tests/test_config.py
git commit -m "feat: openai 依赖 + LLM provider 配置 (DeepSeek/qwen-vl)"
```

---

## Task 2: labeling.py 新增双路函数 + 合并去重

**Files:**
- Modify: `sidecar/llm/labeling.py`（新增函数，**不删不改**现有 anthropic 的 `label_material`/`_get_client`/`LABEL_TOOL`/`_build_system`/`_encode_image`）
- Test: `tests/test_label_job.py`（新增测试，保留旧 test_label_material_parses_tool_use）

**Interfaces:**
- Consumes: `sidecar.config`（Task 1）
- Produces: `_parse_labels(text)`, `_get_text_client()`, `_get_vision_client()`, `label_with_text(title, content, taxonomy)`, `label_with_vision(image_path, taxonomy, focus_dims)`, `_merge_labels(text_labels, vision_labels)`, `_encode_image_block(path)`。**不改** `label_material`（Task 3 才换）。

- [ ] **Step 1: 写失败测试（追加到 tests/test_label_job.py 末尾）**

在 `tests/test_label_job.py` 末尾追加：
```python
import os
from pathlib import Path

def _fake_chat_client(json_text: str):
    """Mock an openai client: client.chat.completions.create(...) -> resp.choices[0].message.content"""
    class Resp:
        class Choice:
            class Msg:
                content = json_text
            message = Msg()
        choices = [Choice()]
    class Client:
        @property
        def chat(self): return self
        @property
        def completions(self): return self
        def create(self, **kw): return Resp()
    return Client()

def test_parse_labels_valid_json():
    text = '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.9,"out_of_taxonomy":false}]}'
    labels = L._parse_labels(text)
    assert len(labels) == 1
    assert labels[0]["value"] == "风景震撼"

def test_parse_labels_extracts_from_noise():
    text = '思考中...\n{"labels":[{"dimension":"route","value":"赛里木湖","confidence":0.8,"out_of_taxonomy":false}]}\n完毕'
    labels = L._parse_labels(text)
    assert len(labels) == 1
    assert labels[0]["value"] == "赛里木湖"

def test_parse_labels_invalid_returns_empty():
    assert L._parse_labels("not json at all") == []
    assert L._parse_labels("") == []

def test_label_with_text(monkeypatch):
    monkeypatch.setattr(L, "_get_text_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.9,"out_of_taxonomy":false}]}'
    ))
    result = L.label_with_text("赛里木湖", "湖很蓝", [{"name":"content_type","values":["风景震撼"]}])
    assert len(result) == 1
    assert result[0]["value"] == "风景震撼"
    assert result[0]["confidence"] == 0.9
    assert result[0]["source"] == "ai_text"

def test_label_with_vision(monkeypatch, tmp_path):
    # 造一张假图
    img = tmp_path / "t.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fake")
    monkeypatch.setattr(L, "_get_vision_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"route","value":"赛里木湖","confidence":0.85,"out_of_taxonomy":false}]}'
    ))
    result = L.label_with_vision(img, [{"name":"route","values":["赛里木湖"]}], focus_dims=["route"])
    assert len(result) == 1
    assert result[0]["value"] == "赛里木湖"
    assert result[0]["source"] == "ai_vision"

def test_merge_labels_dedup_keeps_higher_confidence():
    text_labels = [
        {"dimension":"route","value":"赛里木湖","confidence":0.5,"out_of_taxonomy":False,"source":"ai_text"},
    ]
    vision_labels = [
        {"dimension":"route","value":"赛里木湖","confidence":0.85,"out_of_taxonomy":False,"source":"ai_vision"},
        {"dimension":"content_type","value":"风景震撼","confidence":0.9,"out_of_taxonomy":False,"source":"ai_vision"},
    ]
    merged = L._merge_labels(text_labels, vision_labels)
    by_key = {(m["dimension"], m["value"]): m for m in merged}
    assert len(merged) == 2
    # 同 (route, 赛里木湖) 取高 confidence 的 vision 那条
    assert by_key[("route","赛里木湖")]["confidence"] == 0.85
    assert by_key[("route","赛里木湖")]["source"] == "ai_vision"
    assert by_key[("content_type","风景震撼")]["source"] == "ai_vision"
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_label_job.py -v`
Expected: 旧 1 个通过，新 6 个 FAIL（`_parse_labels` 等不存在）

- [ ] **Step 3: 在 labeling.py 新增函数（不删现有 anthropic 代码）**

在 `sidecar/llm/labeling.py` **末尾**追加（保留文件顶部原有的 import Anthropic/MODEL/LABEL_TOOL/_get_client/_build_system/_encode_image/label_material 不动）：
```python
# ── 新 provider: openai 兼容 (DeepSeek 文本 + Ollama qwen-vl 视觉) ──
import json
import re
from openai import OpenAI
from sidecar import config

def _parse_labels(text: str) -> list:
    """从模型输出解析标签列表。先 json.loads，失败则正则提取首个 JSON 对象。"""
    if not text:
        return []
    text = text.strip()
    try:
        obj = json.loads(text)
        return obj.get("labels", [])
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        obj = json.loads(m.group(0))
        return obj.get("labels", [])
    except Exception:
        return []

def _get_text_client():
    if not config.TEXT_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置")
    return OpenAI(base_url=config.TEXT_API_BASE, api_key=config.TEXT_API_KEY)

def _get_vision_client():
    return OpenAI(base_url=config.VISION_API_BASE, api_key=config.VISION_API_KEY)

def _build_taxonomy_prompt(taxonomy: list, focus_dims=None) -> str:
    lines = ["可用标签体系如下，只能从中选值；若都不合适，标记 out_of_taxonomy=true 并给出建议值。", ""]
    for dim in taxonomy:
        vals = "、".join(dim["values"])
        lines.append(f"维度 {dim['name']}（{dim.get('description','')}）: {vals}")
    lines.append("")
    if focus_dims:
        lines.append(f"请重点针对以下维度判断：{'、'.join(focus_dims)}")
    lines.append("输出规则：只输出 JSON，格式 {\"labels\":[{\"dimension\":str,\"value\":str,\"confidence\":float(0-1),\"out_of_taxonomy\":bool}]}；给出至少 1 个标签。")
    return "\n".join(lines)

def label_with_text(title: str, content: str, taxonomy: list) -> list:
    """DeepSeek 文本打标（JSON mode）。返回标签，每条带 source='ai_text'。"""
    client = _get_text_client()
    system = "你是一个小红书新疆旅游内容标注助手。" + _build_taxonomy_prompt(taxonomy)
    resp = client.chat.completions.create(
        model=config.TEXT_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"标题：{title}\n\n正文：{content}"},
        ],
    )
    text = resp.choices[0].message.content or ""
    labels = _parse_labels(text)
    for lb in labels:
        lb["source"] = "ai_text"
    return labels

def _encode_image_block(path) -> dict:
    """OpenAI 视觉格式的 image block（data URL）。"""
    data = base64.standard_b64encode(Path(path).read_bytes()).decode()
    ext = Path(path).suffix.lstrip(".").lower()
    media = "jpeg" if ext in ("jpg", "jpeg") else ext or "jpeg"
    return {"type": "image_url", "image_url": {"url": f"data:image/{media};base64,{data}"}}

def label_with_vision(image_path, taxonomy: list, focus_dims=None) -> list:
    """本地 qwen-vl 看图打标。返回标签，每条带 source='ai_vision'。"""
    client = _get_vision_client()
    system = "你看一张小红书新疆旅游笔记的图片，判断内容标签。" + _build_taxonomy_prompt(taxonomy, focus_dims)
    user_content = [
        {"type": "text", "text": "请根据图片判断标签，只输出 JSON。"},
        _encode_image_block(image_path),
    ]
    resp = client.chat.completions.create(
        model=config.VISION_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    text = resp.choices[0].message.content or ""
    labels = _parse_labels(text)
    for lb in labels:
        lb["source"] = "ai_vision"
    return labels

def _merge_labels(text_labels: list, vision_labels: list) -> list:
    """合并两路标签，按 (dimension,value) 去重，保留 confidence 更高（及其 source）的那条。"""
    merged = {}
    for lb in text_labels + vision_labels:
        key = (lb.get("dimension"), lb.get("value"))
        if key not in merged:
            merged[key] = lb
        else:
            if lb.get("confidence", 0) > merged[key].get("confidence", 0):
                merged[key] = lb
    return list(merged.values())
```

注意顶部需要 `import base64`（原文件已有）和 `from pathlib import Path`（原文件已有），不重复加。

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_label_job.py -v`
Expected: 全绿（旧 1 + 新 6 = 7）

- [ ] **Step 5: 全量套件无回归**

Run: `.venv/bin/python -m pytest -v`
Expected: 全绿 pristine

- [ ] **Step 6: Commit**

```bash
git add sidecar/llm/labeling.py tests/test_label_job.py
git commit -m "feat: labeling 双路函数 (DeepSeek 文本 + qwen-vl 视觉) + 合并去重"
```

---

## Task 3: label_material 改为串行编排，移除 anthropic 代码

**Files:**
- Modify: `sidecar/llm/labeling.py`（删除 anthropic 专属代码，替换 `label_material`）
- Modify: `tests/test_label_job.py`（重写 `test_label_material_parses_tool_use`，删除旧 mock，新增编排测试）

**Interfaces:**
- Consumes: Task 2 的 `label_with_text`/`label_with_vision`/`_merge_labels`，`config.VISION_TRIGGER_CONFIDENCE`/`VISION_MAX_IMAGES`
- Produces: `label_material(title, content, image_paths, taxonomy) -> list`（新实现：文本 → 触发判断 → 视觉 → 合并）。签名不变（label.py 调用方不变）。

- [ ] **Step 1: 重写 tests/test_label_job.py 的编排测试**

把 `tests/test_label_job.py` 里旧的 `test_label_material_parses_tool_use`（anthropic mock）**删除**，替换为以下编排测试（保留 Task 2 加的 _fake_chat_client 等辅助函数和其余测试）：
```python
def test_label_material_skips_vision_when_confident(monkeypatch):
    # 文本全高置信度 → 不触发视觉
    monkeypatch.setattr(L, "_get_text_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.9,"out_of_taxonomy":false}]}'
    ))
    called = {"vision": False}
    def boom(image_path, taxonomy, focus_dims=None):
        called["vision"] = True
        return []
    monkeypatch.setattr(L, "label_with_vision", boom)
    result = L.label_material("赛里木湖", "湖很蓝", [], [{"name":"content_type","values":["风景震撼"]}])
    assert called["vision"] is False
    assert len(result) == 1
    assert result[0]["source"] == "ai_text"

def test_label_material_triggers_vision_on_low_confidence(monkeypatch, tmp_path):
    img = tmp_path / "t.jpg"
    img.write_bytes(b"\xff\xd8fake")
    # 文本有个低置信度标签 → 触发视觉，视觉补一条
    monkeypatch.setattr(L, "_get_text_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.4,"out_of_taxonomy":false}]}'
    ))
    monkeypatch.setattr(L, "_get_vision_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"route","value":"赛里木湖","confidence":0.85,"out_of_taxonomy":false}]}'
    ))
    result = L.label_material("赛里木湖", "湖很蓝", [img], [{"name":"content_type","values":["风景震撼"]},{"name":"route","values":["赛里木湖"]}])
    # 合并后 2 条：文本的风景震撼(0.4) + 视觉的赛里木湖(0.85)
    assert len(result) == 2
    sources = {r["source"] for r in result}
    assert sources == {"ai_text", "ai_vision"}

def test_label_material_vision_failure_degrades_gracefully(monkeypatch, tmp_path):
    img = tmp_path / "t.jpg"
    img.write_bytes(b"\xff\xd8fake")
    monkeypatch.setattr(L, "_get_text_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.4,"out_of_taxonomy":false}]}'
    ))
    def boom(image_path, taxonomy, focus_dims=None):
        raise RuntimeError("ollama down")
    monkeypatch.setattr(L, "label_with_vision", boom)
    result = L.label_material("赛里木湖", "湖很蓝", [img], [{"name":"content_type","values":["风景震撼"]}])
    # 视觉挂了 → 降级只用文本
    assert len(result) == 1
    assert result[0]["source"] == "ai_text"

def test_label_material_no_image_skips_vision(monkeypatch):
    # 低置信度但没有图 → 跳过视觉，仅返回文本标签
    monkeypatch.setattr(L, "_get_text_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.4,"out_of_taxonomy":false}]}'
    ))
    result = L.label_material("赛里木湖", "湖很蓝", [], [{"name":"content_type","values":["风景震撼"]}])
    assert len(result) == 1
    assert result[0]["source"] == "ai_text"
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_label_job.py -v`
Expected: 新编排测试 FAIL（label_material 还是 anthropic 版）

- [ ] **Step 3: 替换 label_material，删除 anthropic 代码**

把 `sidecar/llm/labeling.py` 顶部 anthropic 专属部分（`from anthropic import Anthropic`/`MODEL`/`_get_client`/`LABEL_TOOL`/`_build_system`/旧 `_encode_image`/旧 `label_material`）**全部删除**，替换为新编排版。最终文件顶部应为：
```python
import base64
import json
import re
from pathlib import Path
from openai import OpenAI
from sidecar import config


def _parse_labels(text: str) -> list:
    if not text:
        return []
    text = text.strip()
    try:
        return json.loads(text).get("labels", [])
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0)).get("labels", [])
    except Exception:
        return []


def _get_text_client():
    if not config.TEXT_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置")
    return OpenAI(base_url=config.TEXT_API_BASE, api_key=config.TEXT_API_KEY)


def _get_vision_client():
    return OpenAI(base_url=config.VISION_API_BASE, api_key=config.VISION_API_KEY)


def _build_taxonomy_prompt(taxonomy: list, focus_dims=None) -> str:
    lines = ["可用标签体系如下，只能从中选值；若都不合适，标记 out_of_taxonomy=true 并给出建议值。", ""]
    for dim in taxonomy:
        vals = "、".join(dim["values"])
        lines.append(f"维度 {dim['name']}（{dim.get('description','')}）: {vals}")
    lines.append("")
    if focus_dims:
        lines.append(f"请重点针对以下维度判断：{'、'.join(focus_dims)}")
    lines.append("输出规则：只输出 JSON，格式 {\"labels\":[{\"dimension\":str,\"value\":str,\"confidence\":float(0-1),\"out_of_taxonomy\":bool}]}；给出至少 1 个标签。")
    return "\n".join(lines)


def label_with_text(title: str, content: str, taxonomy: list) -> list:
    client = _get_text_client()
    system = "你是一个小红书新疆旅游内容标注助手。" + _build_taxonomy_prompt(taxonomy)
    resp = client.chat.completions.create(
        model=config.TEXT_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"标题：{title}\n\n正文：{content}"},
        ],
    )
    text = resp.choices[0].message.content or ""
    labels = _parse_labels(text)
    for lb in labels:
        lb["source"] = "ai_text"
    return labels


def _encode_image_block(path) -> dict:
    data = base64.standard_b64encode(Path(path).read_bytes()).decode()
    ext = Path(path).suffix.lstrip(".").lower()
    media = "jpeg" if ext in ("jpg", "jpeg") else ext or "jpeg"
    return {"type": "image_url", "image_url": {"url": f"data:image/{media};base64,{data}"}}


def label_with_vision(image_path, taxonomy: list, focus_dims=None) -> list:
    client = _get_vision_client()
    system = "你看一张小红书新疆旅游笔记的图片，判断内容标签。" + _build_taxonomy_prompt(taxonomy, focus_dims)
    user_content = [
        {"type": "text", "text": "请根据图片判断标签，只输出 JSON。"},
        _encode_image_block(image_path),
    ]
    resp = client.chat.completions.create(
        model=config.VISION_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    text = resp.choices[0].message.content or ""
    labels = _parse_labels(text)
    for lb in labels:
        lb["source"] = "ai_vision"
    return labels


def _merge_labels(text_labels: list, vision_labels: list) -> list:
    merged = {}
    for lb in text_labels + vision_labels:
        key = (lb.get("dimension"), lb.get("value"))
        if key not in merged:
            merged[key] = lb
        elif lb.get("confidence", 0) > merged[key].get("confidence", 0):
            merged[key] = lb
    return list(merged.values())


def label_material(title: str, content: str, image_paths: list, taxonomy: list) -> list:
    """串行编排：DeepSeek 文本打标 → 低置信度触发 qwen-vl 看图补 → 合并去重。"""
    text_labels = label_with_text(title, content, taxonomy)

    low_conf = [lb for lb in text_labels if lb.get("confidence", 0) < config.VISION_TRIGGER_CONFIDENCE]
    imgs = [Path(p) for p in image_paths[:config.VISION_MAX_IMAGES] if Path(p).exists()]
    if not low_conf or not imgs:
        return text_labels

    focus_dims = list({lb["dimension"] for lb in low_conf})
    try:
        vision_labels = label_with_vision(imgs[0], taxonomy, focus_dims=focus_dims)
    except Exception:
        # 视觉降级：仅用文本标签
        return text_labels
    return _merge_labels(text_labels, vision_labels)
```

注意：新代码不直接用 `os`（config 读 env），故顶部不 import os。

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_label_job.py -v`
Expected: 全绿（Task 2 的 6 个 + Task 3 的 4 个编排测试）

- [ ] **Step 5: 全量套件无回归**

Run: `.venv/bin/python -m pytest -v`
Expected: 全绿 pristine（test_label_flow.py mock 的是 label_material，仍通过）

- [ ] **Step 6: 确认 labeling.py 不再 import anthropic**

Run: `grep -n anthropic sidecar/llm/labeling.py`
Expected: 无输出（anthropic 已从 labeling 移除）

- [ ] **Step 7: Commit**

```bash
git add sidecar/llm/labeling.py tests/test_label_job.py
git commit -m "feat: label_material 改为 DeepSeek+qwen-vl 串行编排, 移除 anthropic"
```

---

## Task 4: label.py 传播 source + 测试断言

**Files:**
- Modify: `sidecar/jobs/label.py:67`（`source="ai"` → `source=lb.get("source","ai_text")`）
- Modify: `tests/test_label_flow.py`（断言 source 写入正确）

**Interfaces:**
- Consumes: Task 3 的 `label_material`（返回的 label 带 `source`）
- Produces: `material_tag.source` 写入 `ai_text`/`ai_vision`

- [ ] **Step 1: 修改 tests/test_label_flow.py 断言 source**

`tests/test_label_flow.py` 现有的 `test_run_label_job_writes_tags` **不改**（其 fake_label 不带 source，label.py 默认 `ai_text`，断言 `confirmed_by_human`/count 仍通过）。

在文件**末尾追加**一个新测试（断言 source 写入 DB）：
```python
def test_source_propagated_to_material_tag(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr("sidecar.config.DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr("sidecar.config.MEDIA_DIR", tmp_path / "media")
    seed.seed_taxonomy()
    imp.import_folder(Path(__file__).parent / "fixtures" / "import_root")

    def fake_label(title, content, image_paths, taxonomy):
        return [
            {"dimension": "content_type", "value": "风景震撼", "confidence": 0.9, "out_of_taxonomy": False, "source": "ai_text"},
            {"dimension": "content_type", "value": "测试视觉标签", "confidence": 0.8, "out_of_taxonomy": True, "source": "ai_vision"},
        ]
    monkeypatch.setattr(labeljob, "label_material", fake_label)

    from sidecar.db.session import get_session
    from sidecar.db.models import ScrapeJob, MaterialTag
    s = get_session()
    job = ScrapeJob(type="label_batch", status="queued", params={})
    s.add(job); s.commit()

    labeljob.run_label_job(job.id)

    s2 = get_session()
    tags = s2.query(MaterialTag).all()
    # 风景震撼是 in-taxonomy → MaterialTag，source=ai_text
    mt = [t for t in tags]
    assert any(t.source == "ai_text" for t in mt), f"expected ai_text source, got {[t.source for t in mt]}"
```
注意：现有文件 `from pathlib import Path` 在文件底部（历史遗留），pytest 运行时已 import 全模块故可用；本任务不动它，新测试直接用 `Path` 即可。

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_label_flow.py::test_source_propagated_to_material_tag -v`
Expected: FAIL（label.py 还写 source="ai"）

- [ ] **Step 3: 修改 sidecar/jobs/label.py 第 67 行**

把：
```python
                s.add(MaterialTag(
                    material_id=m.id, tag_value_id=tv.id, source="ai",
                    confidence=conf, confirmed_by_human=False))
```
改为：
```python
                s.add(MaterialTag(
                    material_id=m.id, tag_value_id=tv.id, source=lb.get("source", "ai_text"),
                    confidence=conf, confirmed_by_human=False))
```
（行号会因上下文略有偏移，按代码内容定位：`source="ai"` 那一处。）

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_label_flow.py -v`
Expected: 全绿

- [ ] **Step 5: 全量套件无回归**

Run: `.venv/bin/python -m pytest -v`
Expected: 全绿 pristine

- [ ] **Step 6: Commit**

```bash
git add sidecar/jobs/label.py tests/test_label_flow.py
git commit -m "feat: material_tag.source 区分 ai_text/ai_vision"
```

---

## Task 5: 真实 e2e 冒烟（DeepSeek + Ollama）

**Files:** 无代码改动（验证）

**Interfaces:** 验证 spec §10 验收标准。

- [ ] **Step 1: 确认 Ollama 在跑 + qwen3-vl 可用**

Run: `curl -s --noproxy '*' --max-time 5 http://localhost:11434/api/tags | python3 -c "import json,sys;d=json.load(sys.stdin);print([m['name'] for m in d.get('models',[])])"`
Expected: 列表含 `qwen3-vl:8b`。若没有，`ollama pull qwen3-vl:8b`（用户机器已有，应直接通过）。

- [ ] **Step 2: 确认 DEEPSEEK_API_KEY 已设**

Run: `echo "${DEEPSEEK_API_KEY:+set (len ${#DEEPSEEK_API_KEY})}" || echo "NOT SET"`
Expected: `set (len N)`。若 NOT SET，提示用户 `export DEEPSEEK_API_KEY="sk-..."`（用户已有 key，确认在当前 shell 可见；若不在 rc 文件里，需用户 source）。

- [ ] **Step 3: 起一个 sidecar，用真实 provider 单条打标验证**

写一个临时验证脚本 `/tmp/e2e_label.py`（不进 git）：
```python
import sys, json
sys.path.insert(0, "/Users/aicer/Documents/Project/xinjiang-acquisition-workbench")
from sidecar.db.session import get_session
from sidecar.db.models import Material, TagDimension
from sidecar.llm.labeling import label_material

s = get_session()
m = s.query(Material).first()
tax = [{"name": d.name, "description": d.description, "values": [v.value for v in d.values if v.status=="active"]} for d in s.query(TagDimension).all()]
img_paths = []
# 找第一张图
if m.images:
    from sidecar import config
    img_paths = [config.MEDIA_DIR / m.images[0].path]
print(f"素材: {m.title[:40]} (id={m.id}), 图: {len(img_paths)}")
labels = label_material(m.title, m.content, img_paths, tax)
print("标签:")
for lb in labels:
    print(f"  [{lb.get('source')}] {lb.get('dimension')}={lb.get('value')} conf={lb.get('confidence')} oot={lb.get('out_of_taxonomy')}")
```
Run: `.venv/bin/python /tmp/e2e_label.py`
Expected: 打印该素材的标签，每条带 `source`（`ai_text`，低置信度的应有 `ai_vision`）。验证：
- DeepSeek 调通（出 ai_text 标签）
- 若有低置信度标签 + 有图，qwen-vl 也调通（出 ai_vision 标签）
- 无 key 报错信息清晰（若 key 没设，会抛 `DEEPSEEK_API_KEY 未设置`）

- [ ] **Step 4: 清理临时脚本 + 确认无残留进程**

Run: `rm -f /tmp/e2e_label.py && pgrep -f 'sidecar.app' | head`
Expected: 无残留 sidecar 进程

- [ ] **Step 5: 全量套件最终确认**

Run: `.venv/bin/python -m pytest -v`
Expected: 全绿 pristine

- [ ] **Step 6: Commit（若有 e2e 记录文件则加，否则空 commit 标记完成）**

```bash
cd ~/Documents/Project/xinjiang-acquisition-workbench
git commit --allow-empty -m "chore: LLM provider 切换 e2e 验证通过 (DeepSeek + qwen-vl)"
```

---

## 验收标准（spec §10 对照）

1. ✅ `DEEPSEEK_API_KEY` 设好后打标出标签 — Task 5 Step 3
2. ✅ 标签 source 为 `ai_text` 或 `ai_vision` — Task 4 + Task 5
3. ✅ 低置信度触发视觉补标 — Task 5 Step 3（日志/输出可见 ai_vision）
4. ✅ Ollama 没起时降级不崩 — Task 3 test_label_material_vision_failure_degrades_gracefully
5. ✅ 全测试通过 pristine — 各 Task
6. ✅ labeling 不再调 anthropic — Task 3 Step 6

---

## 备注

- 触发逻辑仅按置信度（spec §3 的"维度缺失"条款已舍弃，理由见 Global Constraints）。
- 视觉只看首图（`VISION_MAX_IMAGES=1`）。
- `anthropic` 包保留在 pyproject，不删（spec §6）。
- DeepSeek 旧模型名 deepseek-chat/reasoner 2026/07/24 下线，本计划直接用 deepseek-v4-pro。
