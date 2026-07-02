# 交接文档 — 模块 A v0.3 收尾（问题池+合成库提质 + 抓取/增量）

> 写于 2026-07-02（v0.3 进行中）。v0.2 已合并 main。本会话在 `feat/module-A-v0.3` 上推进 A 的 v0.3 收尾清单。
> 读此文件 + `.superpowers/sdd/progress.md` + `docs/superpowers/specs/2026-07-02-module-A-v0.2-design.md`（v0.2）即可接上。模块全景见 `docs/superpowers/specs/2026-06-28-workbench-module-A-design.md` §9（A~F 六大模块，目前只做了 A）。

## 项目
- `/Users/aicer/Documents/Project/xinjiang-acquisition-workbench`
- 当前分支：`feat/module-A-v0.3`（基于 main=b006a03）。main 已含 v0.2。
- Tauri+React+Python sidecar 桌面工具，新疆旅游获客工作台。
- **无 remote**，纯本地。

## v0.3 收尾清单进度
- ✅ **B1 合成库 prompt 提质**：synthesize_prompt 补 few-shot 正/反例 + 反套话约束；实测产出从"五感治愈"套话→"iPhone16Pro 逆光-0.7曝光"等具体文案。顺手硬化 `_parse_obj`（推理模型 MiniMax-M3 思考带花括号致贪婪正则误并→返回{}的间歇失败）：去 markdown 围栏 + 扫顶层平衡 `{...}` 取最长。修了 test_task_config_defaults 的 .env 污染隔离 bug。commit `51a02f2`。
- ✅ **B2 问题池阈值**：在 313 条 embedding 上扫阈值，**结论是 0.78 不动**——降阈值触发链式合并（0.72 时 193/313 挤一簇）且单问题簇占比不降。config 加注释 + 测试锁住传递闭包行为。commit `eb4f409`。
- ✅ **C1 长 job 改独立短 session**：`db/session.py` 加 `session_scope()`；question_pool/label/synthesis 三 job 重构，LLM 调用期间不持有 session，根治 /jobs 偶发卡死。`_log` 改独立短 session 立即 commit → 日志即时可见（修了 Stage1 期间 DB 看不到进度的监控盲区）。commit `c6cdfac`。
- ✅ **C2 前端 MINOR 债**：Synthesis extract 加 catch + setTimeout 清理 + useEffect race-guard；Questions race-guard + rename 清空输入 + source_ref null 守卫。commit `5514abf`。
- 🔄 **A1 抓取任务表单 UI + job**（spec §8 v0.3 项）：`sidecar/opencli/runner.py` 有 runner 未接 job/API/UI；需包 scrape job + `POST /jobs/scrape` + 表单。
- 🔄 **A2 Flow C 增量聚类 + 周报**（spec §8 v0.3 项）：question_pool 支持 `mode=incremental`（新评论 embed→匹配现有簇/建新簇）+ 周报。
- 测试：76/76 绿（`.venv/bin/python -m pytest -v`，**必须 `arch -arm64` 前缀**，见下）。

## 关键架构点（踩坑必读）
- **Claude Code 的 Bash 跑在 Rosetta x86_64**，但项目 `.venv` 的包是 arm64-only（`pydantic_core` 等编译扩展）。直接 `.venv/bin/python` 会 ImportError。**解法：`arch -arm64 .venv/bin/python ...`**（系统 python3.13 是 universal2，arch -arm64 强制 arm64 slice，包正常加载）。已存记忆 `run-arm64-venv-via-arch`。**装** pip 原生二进制仍须用户自己在 arm64 终端跑（`!` 前缀），Claude 代装会污染。
- 跑 sidecar：`arch -arm64 .venv/bin/python -m sidecar.app --port <port>`（NO_PROXY 给 ollama 绕代理在 app.py import 时设）。
- 跑 Tauri：`arch -arm64 npm run tauri dev`（压整棵树 arm64，否则 Tauri spawn 的 sidecar 是 x64 → pydantic 崩）。target/ 已有 arm64 产物，cargo 增量快。
- **本地有 Clash 代理 127.0.0.1:7890**：外网(DeepSeek/MiniMax)走代理，localhost(ollama) 必须 NO_PROXY 绕过（app.py 已设）。
- 机器：Apple M5 Pro arm64。

## MiniMax 实测时序（校准过，别再用 HANDOFF 旧版 0.8s/条）
- 冷启动单次调用 ~9s/条（冷启动开销主导，别拿单次外推）。
- 全量冷启动 job 实测 **~27 分钟**（644 评论→313 问题→171 簇），不是 2-3h。Stage1~8min, Stage2~8min, Stage3-4 即时, Stage5~11min。
- `.env`：`MINIMAX_API_KEY`(125 chars) / `MINIMAX_API_BASE=https://api.minimaxi.com/v1` / `MINIMAX_MODEL=MiniMax-M3` 已配好。

## 怎么继续（新会话第一句话）
> 项目在 /Users/aicer/Documents/Project/xinjiang-acquisition-workbench，读 docs/HANDOFF.md。接着做 v0.3 的 A1（抓取 job）或 A2（增量聚类）。
