# 新疆定制游获客工作台 · 模块 A 设计

> 版本: v0.1-design (2026-06-28)
> 范围: 6 模块工作台的第 1 个模块「素材库 + 问题池管家」
> 后续模块（B 内容工厂 / C 咨询应答 / D 发布反馈 / E 广告 Agent / F 编排）单独写 spec

---

## 1. 背景与定位

### 1.1 商业目标
做新疆定制游获客。来源参考与 ChatGPT 讨论的 6 阶段路径（详见 LLM 知识库 `00-Inbox/ChatGPT 输出/新疆定制游获客策略.md`）：

> 素材库 → 问题池 → 人工测试 → 内容工厂 → 销售 Agent → 广告 Agent

ChatGPT 标红的真正资产：**需求数据库 + 客户咨询数据 + 成交案例数据**。

### 1.2 工具定位
**不是单一 Agent，是演进式工作台**。第一版只交付 1 个模块，UI/数据/调度框架预留 5 个扩展位。每验证完一个阶段才装下一个模块，避免做出"6 个 Demo 的玩具"。

### 1.3 与 Obsidian 知识库的关系
**完全独立**。本工具是业务运营工具，数据库 SQLite 本地存。Obsidian 那套判别器/Parser 架构不复用、不交叉。

---

## 2. 模块 A 范围

### 2.1 模块 A 解决的问题
1. 已抓取的 30 篇小红书素材是孤立 markdown 文件，没结构、不好检索、不能交叉分析
2. 问题池（ChatGPT 钦点的"未来 Agent 知识库"）完全没建
3. 标题/卖点/钩子/CTA 库不存在，下游内容生产无种子

### 2.2 模块 A 交付的资产
- **结构化素材库** — 含多维标签（内容类型/季节/受众/路线/价格/情绪...）
- **可演化的标签体系** — AI 提议、人确认
- **问题池** — 从评论 + 多平台问答抽取、归一化、聚类
- **合成库** — 标题 / 卖点 / 钩子 / CTA 四类合成物，可追溯到来源素材

### 2.3 不在模块 A 范围
- 内容生成（模块 B）
- 客户消息处理（模块 C）
- 自动发布（模块 D）
- 广告投放（模块 E）
- 多平台抓取（仅小红书闭环；抖音/知乎留到 v0.4+）
- 多人协作

---

## 3. 技术架构

### 3.1 选型概览

| 层 | 选择 | 理由 |
|---|---|---|
| Shell | Tauri (Rust) | 安装包小（~10MB），原生 webview，未来分发友好 |
| 前端 | React + Vite + TypeScript | 生态成熟，类型安全（与 sidecar schema 对齐） |
| Sidecar | Python + FastAPI | 复用 opencli + LLM SDK；Tauri spawn 子进程 RPC |
| DB | SQLite | 单机零运维，Python/JS 均有成熟 ORM |
| ORM | SQLAlchemy + alembic | 迁移友好 |
| LLM | Claude API (text + vision) | Vision 强、Prompt caching 省钱；client 可换 |
| 媒体 | 本地文件 `./data/media/<note_id>/` | 不入库 |

### 3.2 系统拓扑

```
┌─────────────── Tauri Shell (Rust) ──────────────────┐
│                                                     │
│   React 前端 (Vite + TS)                            │
│      ├ /materials  素材库（表格 / 画廊 / 详情）       │
│      ├ /tags       标签体系                         │
│      ├ /questions  问题池                           │
│      ├ /synthesis  合成库（标题/卖点/钩子/CTA）       │
│      └ /jobs       任务中心                         │
│                            ↕ HTTP (localhost)        │
│   Python sidecar (FastAPI on 127.0.0.1:<port>)      │
│      ├ opencli runner  (subprocess)                 │
│      ├ LLM client      (Claude + prompt caching)    │
│      ├ DB layer        (SQLAlchemy + SQLite)        │
│      └ Async job queue (in-process; asyncio)        │
│                            ↕                         │
│   SQLite ./data/data.db  +  ./data/media/<id>/      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 3.3 Sidecar 通信
- Tauri 启动时 spawn `python -m sidecar.app --port <random>`
- 端口通过 stdout 返回给 Tauri，再注入前端 `import.meta.env.VITE_SIDECAR_PORT`
- 退出时 Tauri 发送 SIGTERM，sidecar gracefully 关闭

---

## 4. 数据模型

### 4.1 表清单

```
[抓取层]
  material         素材笔记主表
  material_image   笔记的图片（路径 + 顺序）
  comment          评论（问题池源料）

[标签层]
  tag_dimension    标签维度（如 内容类型/季节/受众）
  tag_value        标签值（含 alias 同义词数组）
  material_tag     素材↔标签 关联（含 AI/人 来源 + confidence）

[问题池]
  question         单条问题（归一化 + 来源回溯）
  question_cluster 问题聚类（10 大类）

[合成物]
  asset            标题/卖点/钩子/CTA（含 derived_from）

[任务调度]
  scrape_job       抓取/AI 跑批任务
  tag_suggestion   AI 提议但未入体系的新标签收件箱
```

### 4.2 关键字段设计

**`material_tag` 三态来源追踪**：
```python
material_tag(
    material_id, tag_value_id,
    source: 'ai' | 'human' | 'rule',
    confidence: float | None,        # AI 给的概率
    confirmed_by_human: bool,
    confirmed_at: datetime | None,
)
```
→ 任何时刻可以筛"AI 标了但人没确认的"做批量 review。

**`tag_value.alias`**：JSON 数组，存同义词。合并标签时旧名进 alias。

**`asset.derived_from`**：JSON 数组 of material_id，记录这条卖点是从哪几篇提炼的，未来生成时可回溯"为啥这么写"。

**`question.source_ref`**：回溯到原始评论 ID 或外部 URL（携程问答/知乎...），杜绝 LLM 幻觉。

**`scrape_job` 状态机**：
```
queued → running → done | failed
              ↓
         cancelled
```

完整 schema 在实现阶段由 alembic migration 提交，不在 spec 里展开。

---

## 5. 核心 UI 视图

### 5.1 `/materials` — 素材库（日常主战场）

**布局**：
- 顶栏：搜索框 · 标签多维筛选器 · 排序（点赞/收藏/最新）· 批量操作
- 左 40%：列表（缩略图 + 标题 + 互动数据 + 当前标签 chips）
- 右 60%：详情（正文 + 图片画廊 + 标签编辑面板）

**核心交互**：
- AI 推荐标签以 chip 出现，`confidence < 0.6` 加 `?` 弱化色
- 点击 chip = 确认（变实色）；右键 = 改 / 拒绝 / 转为"建议新标签"
- 批量选择多条 → 批量打同一标签 / 触发 AI 重打标
- 图片画廊横向滚动，点击放大

### 5.2 `/tags` — 标签体系

- 左：维度树（用户可新建维度）
- 右：当前维度下的标签值列表（带命中素材数 + alias 数）
- 操作：合并同义、改名、加 alias、弃用（不硬删）

### 5.3 `/questions` — 问题池

- 左：cluster 树（可多级）
- 中：cluster 下的问题（按 hot_score 排）
- 右：问题详情 + 来源回溯
- 顶部：合并 / 拆分 / 改写归一化 / 新建 cluster

### 5.4 `/synthesis` — 合成库

四 tab：**标题 | 卖点 | 钩子 | CTA**

每条卡片：
- 文本
- 适用标签 chips
- 来源素材链接（点击跳 /materials/<id>）
- [编辑] [删除] [👎 不喜欢]
- 顶部「让 AI 从选中素材里提炼新一批」按钮

### 5.5 `/jobs` — 任务中心

- 抓取 tab：表单触发 opencli 命令（新关键词搜索、抓某条评论、抓某用户主页）
- AI tab：批量打标 / 提炼问题 / 合成卖点
- 进度条 + 失败重试 + 日志查看

---

## 6. AI 工作流

### 6.1 Flow A — 入库 → 自动打标

触发：新素材抓回入库后自动 enqueue。

```
For each new material:
  prompt = system(标签体系 + few-shot) + user(笔记正文 + 首图 vision)
  LLM 返回: { dimension: tag_value, confidence } × N
  
  写 material_tag(source='ai', confirmed_by_human=false)
  confidence < 0.6 标记「待 review」
  
  若 LLM 提议"现有体系外"的标签:
    写入 tag_suggestion 收件箱
```

**Prompt caching 关键设计**：
- 缓存内容：标签体系定义 + 8 条 few-shot 示例（~2-3K tokens）
- 每次只换"待打标的笔记"（~500-1500 tokens）
- 批量 100 条素材，缓存命中率 95%+

### 6.2 Flow B — 标签体系演进

触发：用户主动打开收件箱。

UI：`/tags/inbox` 显示 `tag_suggestion` 表里所有 pending 项。

操作：
- ✓ 接受 → 写入 `tag_value`
- 🔄 合并到现有标签 → 自动给目标标签加 alias
- ✏️ 改名后接受
- ✗ 拒绝（标 dismissed，不再提示）

### 6.3 Flow C — 问题池冷启动 & 增量

**冷启动**（一次性）：
```
全部 comment 表 →
  Stage 1: LLM 过滤"是不是用户问题" → 抽出问题文本
  Stage 2: LLM 归一化（"几月去新疆?" + "什么时候去新疆好" 合并）
  Stage 3: embedding + 层次聚类 → 写 question_cluster
  Stage 4: 人在 UI 上调整 cluster 命名 + 边界
```

**增量**（新抓评论后自动跑）：
```
新 comments →
  Stage 1+2 同上 →
  对每个新 question:
    最近邻 embedding 搜索现有 cluster
    if similarity > threshold: 归入现有
    else: 入 "待聚类" 池
  每周聚一次 "待聚类" 池，提议新 cluster → 人 review
```

---

## 7. 项目结构

```
~/Documents/Project/xinjiang-acquisition-workbench/
├── README.md
├── docs/
│   └── superpowers/specs/
│       └── 2026-06-28-workbench-module-A-design.md   ← 本文档
├── src-tauri/                  # Tauri shell
│   ├── Cargo.toml
│   └── src/main.rs             # spawn sidecar、桥接
├── src/                        # React 前端
│   ├── routes/{materials,tags,questions,synthesis,jobs}/
│   ├── components/             # 通用：标签 chip / 画廊 / 表格
│   ├── api/                    # sidecar RPC 客户端
│   └── types/                  # 与 sidecar 对齐的 schema
├── sidecar/                    # Python sidecar
│   ├── pyproject.toml
│   ├── app.py                  # FastAPI entry
│   ├── db/
│   │   ├── models.py           # SQLAlchemy 11 张表
│   │   └── migrations/         # alembic
│   ├── opencli/                # opencli subprocess wrapper
│   │   ├── runner.py
│   │   └── adapters.py         # search/note/comments/download 封装
│   ├── llm/
│   │   ├── client.py           # Claude client + prompt caching
│   │   ├── prompts/            # 各场景 prompt 模板
│   │   └── schemas.py          # LLM 结构化输出 schema
│   ├── jobs/
│   │   ├── queue.py
│   │   ├── scrape.py
│   │   ├── label.py
│   │   └── cluster.py
│   └── api/
│       ├── materials.py
│       ├── tags.py
│       ├── questions.py
│       ├── synthesis.py
│       └── jobs.py
├── data/                       # 不入 git
│   ├── data.db
│   ├── media/
│   └── logs/
├── scripts/
│   ├── import-from-folder.py   # 导入已抓的 30 篇
│   └── seed-taxonomy.py        # 初始化 6 类标签维度
└── tests/
```

**两个关键脚本**：
1. `import-from-folder.py` 读 `/Users/aicer/Documents/小红书-新疆旅游/` 现有 30 个文件夹，直接写 DB，不重新爬
2. `seed-taxonomy.py` 用 ChatGPT 给的 6 类（风景震撼/避坑攻略/价格透明/行程方案/小众秘境/情绪价值）做初始 `tag_dimension='content_type'` 的种子值

---

## 8. MVP 分版交付

### v0.1 — Must-have（先把价值闭环跑通）
- Tauri 壳跑起来，sidecar spawn + RPC 通
- `import-from-folder.py` 导入 30 篇 + 评论 + 图片路径
- `seed-taxonomy.py` 建初始 6 类标签维度
- `/materials` 视图（表格 + 详情 + 标签编辑）
- Flow A：批量调 LLM 给所有素材打标（vision + text）
- `/jobs` 最简版（job 状态 + 日志）

### v0.2 — Should-have
- `/tags` 视图 + 合并/改名/alias
- Flow C 冷启动：跑完 30 篇的所有评论，建第一版问题池
- `/questions` 视图（cluster 树 + 列表）

### v0.3 — Nice-to-have
- `/synthesis` 视图 + 「AI 提炼卖点/钩子」按钮
- 抓取任务表单 UI（UI 内触发新关键词抓取）
- Flow C 增量聚类 + 周报

### 明确不做（避免范围爆炸）
- 发布功能（模块 D）
- 多账号管理
- 抖音/知乎抓取（小红书闭环优先）
- 多人协作
- 云同步

---

## 9. 模块演进路线

| 模块 | 名称 | 启动条件 | 复用 A 的什么 |
|---|---|---|---|
| **A** | 素材库 + 问题池管家 | **现在** | — |
| **B** | 内容工厂雏形 | A 跑稳 + ≥ 80 条带标素材 | `material` `asset` `tag_value` 全表；prompt 注入合成库 |
| **C** | 咨询应答助手 | 自己发了 30+ 篇内容、有真实私信 | `question` + `cluster` 当知识库；归一化逻辑复用 |
| **D** | 发布 & 反馈 | C 验证转化路径后 | opencli runner、任务中心 |
| **E** | 广告 Agent | 自然流跑通 + 有 CAC/LTV | 任务调度、LLM client、日志体系 |
| **F** | 全栈编排自动化 | 上述全跑通后 | — |

**架构纪律**：
- 每模块作为独立 React route + sidecar 子模块加入，**不动 A 的代码**
- 共享 `material/tag_value/question/asset` 表，UI 组件不共享
- LLM client、opencli runner、job queue **只在 sidecar 一处**，新模块只调用不重写

---

## 10. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 30 条素材点赞分布极不均（1.4w ~ 8），低赞样本未必代表"好" | 标签体系偏掉 | v0.1 后立刻扩到 100 条，加入抖音前观察 |
| AI 标签 confidence 不准 | review 队列堵塞 | 阈值可调；初期人工 review 第一批 30 条做校准 |
| LLM 成本失控 | 烧钱 | 强制 prompt caching；批量任务在 UI 上估算 token 后再执行 |
| opencli 失败/小红书改版 | 抓取全停 | opencli runner 暴露 trace 路径；用 opencli-autofix skill 修复 |
| Tauri+Python sidecar 通信不稳 | 卡顿 | 健康检查 + 自动重启 sidecar；前端有重连逻辑 |
| 标签体系过早收敛 | 后续灵活性差 | 维度可加、标签可弃用不可删；前 200 条素材定期检视体系 |

---

## 11. 验收标准

模块 A 视为"v0.1 完成"的标志：
1. 双击图标启动应用，无报错
2. 30 篇素材在 `/materials` 可见，能筛选/排序
3. 触发"全量打标"任务后 5 分钟内完成，每条素材至少 3 个 AI 推荐标签
4. 可在 UI 上确认/改写/拒绝 AI 标签
5. SQLite 文件可独立用 DB Browser 打开检查

模块 A 视为"v0.3 完成"的标志：
1. v0.1 的全部 +
2. 30 篇评论冷启动后，问题池有 ≥ 50 条问题、≥ 5 个 cluster
3. 在 UI 里输入新关键词能触发抓取，新素材自动打标
4. 合成库里有 ≥ 20 条 AI 提炼的卖点，每条可追溯来源
