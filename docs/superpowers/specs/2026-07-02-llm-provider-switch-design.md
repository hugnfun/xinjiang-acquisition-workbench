# LLM Provider 切换 · DeepSeek + 本地 qwen-vl 设计

> 版本: v0.1-design (2026-07-02)
> 范围: 把模块 A 的打标 LLM 从 Anthropic Claude 切换为 DeepSeek（文本）+ 本地 Ollama qwen3-vl（视觉）双路串行补标
> 动因: 用户要用其他 API（DeepSeek），且本地有 qwen 视觉模型可省 key/钱/不外泄

---

## 1. 背景与目标

### 1.1 现状
模块 A v0.1 的打标 (`sidecar/llm/labeling.py`) 强依赖 Anthropic Claude：
- 用 `anthropic` SDK，硬编码 `MODEL = "claude-sonnet-4-6"`
- 通过 **tool_use** 强制结构化输出（Claude 专有）
- 通过 **vision** 发笔记首图（base64）让模型看图打标
- 用 **prompt caching** (cache_control) 省 token
- API key 读 `ANTHROPIC_API_KEY`

### 1.2 切换原因
- 用户要用 DeepSeek
- DeepSeek 当前主力模型 **看不了图**（纯文本）
- 用户本地有 Ollama 跑的 qwen 视觉模型，可补图、且零成本零外泄

### 1.3 目标
打标流程改为：**DeepSeek 文本打标为主 + 本地 qwen3-vl 看图补标**，串行编排，配置化（env 驱动，可切回 Claude 或换别的）。

---

## 2. 模型路由

| 角色 | 模型 | 接口 | base_url | key |
|---|---|---|---|---|
| 文本打标 | `deepseek-v4-pro` | OpenAI 兼容 | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| 视觉补标 | `qwen3-vl:8b` | OpenAI 兼容（Ollama） | `http://localhost:11434/v1` | 无（本地） |

**关键事实（已验证）**：
- DeepSeek API 模型 ID 是 `deepseek-v4-pro`（小写连字符），不是展示名 "DeepSeek-v4-pro"。
- 旧名 `deepseek-chat` / `deepseek-reasoner` 将于 **2026/07/24 下线**，故用 `deepseek-v4-pro`。
- Ollama 本地实测可达：`localhost:11434/api/tags` 返回 `qwen3-vl:8b`。
- 两个模型都走 OpenAI 兼容接口，sidecar 用 `openai` SDK 统一调用。

---

## 3. 串行补标流程

```
label_material(title, content, image_paths, taxonomy)
   │
   ├─ 1. label_with_text(deepseek)
   │     输入: 标题 + 正文 + taxonomy
   │     输出: [{dimension, value, confidence, out_of_taxonomy}] (JSON mode)
   │
   ├─ 2. 决定要不要看图
   │     条件: 存在 confidence < 0.6 的标签  OR  某些维度完全没给标签
   │     是 → 触发视觉补标；否 → 跳过（纯文本就够）
   │
   ├─ 3. label_with_vision(qwen-vl)  [可选]
   │     输入: 首图（image_paths[0]，base64）+ 那些"拿不准的维度" + taxonomy
   │     输出: [{dimension, value, confidence, out_of_taxonomy}]
   │
   ├─ 4. 合并
   │     两路结果合并，去重（同 dimension+value 取高 confidence 那条）
   │     每条标签记录 source: 'ai_text' 或 'ai_vision'
   │
   └─ 返回合并后的标签列表
```

**触发逻辑（按置信度阈值）**：
- `confidence < 0.6` 的标签 → 视为"拿不准"
- 或 taxonomy 里某维度在文本结果里完全没出现 → 视为"缺失"
- 任一成立 → 调 qwen-vl 针对这些维度看首图补打
- 阈值 `VISION_TRIGGER_CONFIDENCE = 0.6`，走 env 可调

**视觉补标的 prompt 范围**：只让 qwen-vl 针对那些"拿不准/缺失"的维度看图，不全量重打（省本地算力）。

---

## 4. 结构化输出

**不用 tool_use**（Claude 专有，去掉）。两路都靠 prompt 里讲死 schema + 返回 JSON，但约束方式不同：

统一 schema（prompt 里给示例）：
```json
{
  "labels": [
    {"dimension": "content_type", "value": "风景震撼", "confidence": 0.9, "out_of_taxonomy": false},
    {"dimension": "route", "value": "赛里木湖", "confidence": 0.85, "out_of_taxonomy": false}
  ]
}
```

- **DeepSeek（文本）**：用 `response_format={"type":"json_object"}`（其 OpenAI 兼容接口支持），强约束返回合法 JSON。
- **qwen-vl（视觉）**：Ollama 的 OpenAI 兼容接口对 `response_format` 支持不稳，**不用 response_format**；改为 prompt 里强约束 JSON + 解析时容错（提取首个 `{...}` JSON 块，失败则返回空列表不崩）。

两路解析时都走同一个 `_parse_labels(text)` 容错函数（先 json.loads，失败则正则提取首个 JSON 对象）。

---

## 5. 配置（env 驱动，写进 sidecar/config.py）

```python
# 文本模型 (DeepSeek)
TEXT_MODEL = os.environ.get("TEXT_MODEL", "deepseek-v4-pro")
TEXT_API_BASE = os.environ.get("TEXT_API_BASE", "https://api.deepseek.com/v1")
TEXT_API_KEY_ENV = "DEEPSEEK_API_KEY"  # 从此 env 读

# 视觉模型 (本地 Ollama qwen-vl)
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen3-vl:8b")
VISION_API_BASE = os.environ.get("VISION_API_BASE", "http://localhost:11434/v1")
VISION_API_KEY = os.environ.get("VISION_API_KEY", "ollama")  # Ollama 不校验，占位

# 触发阈值
VISION_TRIGGER_CONFIDENCE = float(os.environ.get("VISION_TRIGGER_CONFIDENCE", "0.6"))

# 图片上限（视觉补标只看首图）
VISION_MAX_IMAGES = 1
```

`openai` SDK 创建 client 时分别用各自的 base_url + key。

---

## 6. 改造范围

### 改动
| 文件 | 改动 |
|---|---|
| `sidecar/llm/labeling.py` | **重写**：删 Anthropic tool_use/cache_control/base64 封装；改为 `openai` SDK + 两路函数 + 串行编排 + 合并去重 |
| `sidecar/config.py` | 加 LLM 配置项（上节） |
| `sidecar/jobs/label.py` | `material_tag.source` 写入 `'ai_text'` / `'ai_vision'`（区分两路来源）；其余不变 |
| `pyproject.toml` | 加 `openai>=1.50` 依赖；`anthropic` 保留（不强制删，可后续清理） |
| `tests/test_label_job.py` | 改 mock：mock 两个 openai client（文本 + 视觉），验证串行编排 + 合并逻辑 |

### 不动
- DB schema（`material_tag.source` 已是字符串，加新值即可，不迁移）
- API 路由、前端 UI、Tauri 集成
- 标签维度 taxonomy（seed_taxonomy）
- opencli runner、import、note_md 解析

### 删除的依赖
- `ANTHROPIC_API_KEY` 不再需要（但代码里 `anthropic` 包暂留，不删，避免破坏性改动；后续清理任务再说）

---

## 7. 数据流变化（material_tag.source 语义）

原：所有 AI 标签 `source='ai'`
新：
- `source='ai_text'` — DeepSeek 文本打的
- `source='ai_vision'` — qwen-vl 视觉补的
- 仍都 `confirmed_by_human=False`（等用户 review）

前端 `/materials` 视图的 tag chip 可以后续按 source 加小图标区分（v0.2 polish，本任务不做，只保证数据写对）。

---

## 8. 错误处理

- DeepSeek 调用失败（网络/key/限流）→ `label_with_text` 抛异常，label.py 的 per-material try/except 捕获 → 记 JobLog(error)，该素材跳过（不阻断整批）。已有逻辑（v0.1 修复合批）覆盖。
- qwen-vl 调用失败（Ollama 没起/模型没拉）→ `label_with_vision` 抛异常 → 降级：只用 DeepSeek 的文本标签（记一条 JobLog warn："视觉补标失败，仅用文本标签"），不崩。
- qwen-vl 返回非合法 JSON → 提取 `{...}` 块；仍失败 → 返回空列表，记 warn。

---

## 9. 测试策略

mock 两个 openai client（不真调 API/Ollama）：
- `test_text_labeling`：mock 文本 client 返回 JSON → 解析出 labels
- `test_vision_labeling`：mock 视觉 client 返回 JSON → 解析出 labels
- `test_serial_orchestration_skip_vision`：DeepSeek 全高置信度 → 不触发视觉
- `test_serial_orchestration_trigger_vision`：DeepSeek 有低置信度 → 触发视觉，结果合并去重
- `test_vision_failure_degrades_gracefully`：视觉抛异常 → 只用文本标签，不崩
- `test_merge_dedup`：两路同 dimension+value → 取高 confidence，保留正确 source

label.py 的 `run_label_job` 已有 test，确认 `source` 写入正确值。

---

## 10. 验收标准

1. `DEEPSEEK_API_KEY` 设好后，`npm run tauri dev` → 触发打标 → 30 篇素材出标签
2. 标签 `source` 字段值为 `ai_text` 或 `ai_vision`
3. Ollama 起着时，低置信度的素材会触发视觉补标（日志可见）
4. Ollama 没起时，打标不崩，仅用文本标签
5. 全部测试通过，输出 pristine
6. `anthropic` 不再被 labeling 调用（可保留包）

---

## 11. 不在本范围

- 切换回 Claude 的代码路径（配置已预留 env，但不实现 Claude provider）
- 多 provider 并行 A/B 对比
- 视觉补标看多张图（只看首图）
- 前端按 source 区分展示
- `anthropic` 包的彻底移除
