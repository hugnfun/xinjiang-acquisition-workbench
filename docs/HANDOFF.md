# 交接文档 — Sprint 3 已收尾

> 更新于 2026-07-28。当前分支 `main`，远端 `origin/main`。

## 当前状态

新疆定制游获客工作台采用 Tauri + React + TypeScript 前端和 Python/FastAPI sidecar，数据存储在本地 SQLite。模块 A 及 Sprint 3 内容实验闭环已经完成。

当前真实数据：

- 素材 77 条，评论 6,542 条。
- 问题 2,181 条，问题簇 386 个。
- 合成内容片段 30 条。
- 内容实验 0 条，等待真实发布使用。
- Work Vault 47 条空作者已补全 42 条；剩余 5 条源文件没有作者标记。

## Sprint 3 交付

- `0005_experiments`：内容实验、片段快照、指标快照及 Asset 来源任务迁移。
- 内容实验支持草稿、发布、归档；发布记录组合多个 Asset 并保留不可变文案快照。
- 手工记录浏览、互动、咨询、有效线索、加微信、报价、成交和成交金额，历史快照用于观察增长。
- 分析面板使用每个实验最新快照计算互动率、咨询率、加微率和成交率，避免历史快照重复累加。
- `task_client` 捕获真实 usage，任务失败或取消仍保留已产生用量；合成任务用量精确分摊到 Asset。
- Work Vault 提供作者修复 dry-run 与执行入口，未来导入会自动提取置顶作者。

关键提交：

- `ef804cf` 内容实验与效果指标后端。
- `5363a6e` 内容实验创建、指标与分析界面。
- `d97c023` LLM token/cost 追踪。
- `20fe41d` Work Vault 作者安全回填。

## 验证结果

- `arch -arm64 .venv/bin/python -m pytest -q`：161 passed。
- `npm run build`：通过，38 modules transformed。
- 临时数据库端到端：选择片段 → 创建草稿 → 发布 → 两次指标快照 → 分析汇总，通过。
- 浏览器可视化检查：合成库片段选择、实验创建表单和 KPI 面板正常。

## 运行注意

- Apple Silicon 必须使用 `arch -arm64` 启动 Python sidecar 和 Tauri，避免 Rosetta 与原生 Python 包架构冲突。
- 本地 Ollama 通过 `NO_PROXY` 绕过 Clash；外部 MiniMax/DeepSeek 仍按系统代理访问。
- MiniMax-M3 的计价未硬编码。若 `.env` 没有 `TASK_INPUT_PRICE_CNY_PER_1M` 和 `TASK_OUTPUT_PRICE_CNY_PER_1M`，只展示真实 token，成本显示未配置。
- 作者回填前备份位于 `data/data.db.pre-author-backfill.bak`。

## 下一步

进入真实运营验证：从合成库挑选片段创建实验，发布后在 1/3/7 天录入累计指标。积累足够实验后，再依据问题簇、客群和文案类型比较咨询率与成交率。
