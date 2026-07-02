# 交接文档 — 模块 A v0.2 收尾（问题池 + 合成库）

> 写于 2026-07-02。本会话过长，开新会话继续。读此文件 + `.superpowers/sdd/progress.md` + `docs/superpowers/specs/2026-07-02-module-A-v0.2-design.md` 即可接上。

## 项目
- `/Users/aicer/Documents/Project/xinjiang-acquisition-workbench`
- 分支：`feat/module-A-v0.2`（已合并 main 的内容在 main 上，v0.2 还在 feat 分支）
- Tauri+React+Python sidecar 桌面工具，新疆旅游获客工作台

## 已完成（全部 review 过、测试绿）
- 模块 A v0.1：素材库 + 打标 + 任务中心（main 上）
- LLM provider 切换：打标 DeepSeek，移除 anthropic
- 模块 A v0.2 代码：问题池冷启动 job + 合成库 + 2 视图 + API，67 测试全绿

## 当前状态（关键）
### ✅ 已打通
- DeepSeek 打标：**已完成**，30 篇素材共 317 标签（ai_text 310 + ai_vision 7），在 DB 里
- sidecar 连接：CORS、端口注入(invoke pull)、连接池加大、本地调用绕过代理(NO_PROXY)——全修好了
- MiniMax 接入：`.env` 配好了，**已验证** MiniMax-M3 跑问题池 Stage1，5 条 4.2 秒（比本地27b快23倍）

### ⏳ 待做（新会话直接干这个）
1. **跑问题池冷启动**：`npm run tauri dev` → 任务中心点「问题池冷启动」→ 约 30-40 分钟跑完
   - job 跑时前端 `/jobs` 可能还卡（长job+HTTP共享连接池的残余问题，池已加大到20+50缓解，但偶发卡顿可能还在；可从 DB 直接看进度：`from sidecar.db.models import Question; print(s.query(Question).count())`）
2. **验证问题池**：跑完去「问题池」tab 看簇+AI命名+问题来源
3. **验证合成库**：「合成库」tab 输入素材 id（如 1,2,3）→ 提炼 → 看卖点/钩子/CTA
4. 全部验证 OK 后，feat/module-A-v0.2 合并到 main

## 关键配置（.env，已填好）
- `DEEPSEEK_API_KEY`：打标用
- `MINIMAX_API_KEY` / `MINIMAX_API_BASE=https://api.minimaxi.com/v1` / `MINIMAX_MODEL=MiniMax-M3`：问题池 task_client 用
- embedding 用本地 ollama（qwen3-embedding），免费

## 架构关键点（避免再踩坑）
- **机器是 Apple M5 Pro arm64，但 Claude Code 的 Bash 跑在 Rosetta x64 下** → 装 npm/cargo/pip 原生二进制必须用户自己在 arm64 终端跑（`!` 前缀），Claude 代装会污染（记忆已存）
- **本地有 Clash 代理 127.0.0.1:7890** → sidecar 调 localhost(ollama) 必须 NO_PROXY 绕过（已在 app.py 设），外网(DeepSeek/MiniMax)走代理
- **venv python 是符号链接到系统 python**（正常），但依赖装在 venv site-packages
- **sidecar spawn**：Tauri main.rs 用 `<root>/.venv/bin/python -m sidecar.app --port <free>`，端口通过 `get_sidecar_port` Tauri 命令给前端（invoke，非 eval）
- **长 job 卡 HTTP**：异步 job(asyncio.to_thread) 与 FastAPI 共享 SQLite engine，job 持有 session 久 → 池耗尽。已加大池(20+50)。若还卡，改 job 用独立短 session

## 已知技术债（不阻塞，可后续）
- Jobs.tsx 重复触发防重：已加（job running 时禁用按钮）
- 僵尸 job 清理：sidecar 启动自动清（app.py）
- job 运行时前端 `/jobs` 偶发 load failed：连接池残余，从 DB 直接看进度绕过

## 怎么继续（新会话第一句话）
> 项目在 /Users/aicer/Documents/Project/xinjiang-acquisition-workbench，读 docs/HANDOFF.md。我要跑问题池冷启动验证 MiniMax，帮我盯着进度。
