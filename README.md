# 新疆定制游获客工作台

本地优先的 Tauri + React + FastAPI 桌面工具，用于把小红书素材、评论问题、内容片段和发布效果串成可复盘的获客闭环。

## 当前能力

- 素材抓取、文件夹及 Work Vault 导入，含图片、评论和去重。
- AI 标签体系、人工审核、问题提取、归一化及增量聚类。
- 标题、钩子、卖点和 CTA 合成，支持质量状态与问题簇覆盖分析。
- 内容实验：组合多个内容片段，保存最终发布稿，跟踪发布、咨询、加微、报价、成交及收入指标。
- LLM 后台任务队列、失败重试、取消、日志，以及 token/cost 追踪。

## 本地运行

```bash
source .env
arch -arm64 .venv/bin/python -m sidecar.app --port 8765
```

另开终端运行前端：

```bash
npm install
npm run dev
```

在 Apple Silicon 上运行完整桌面端：

```bash
arch -arm64 npm run tauri dev
```

## 验证

```bash
arch -arm64 .venv/bin/python -m pytest -q
npm run build
```

云端文本任务会记录真实 token。需要估算人民币成本时，在 `.env` 配置：

```bash
TASK_INPUT_PRICE_CNY_PER_1M=<输入单价>
TASK_OUTPUT_PRICE_CNY_PER_1M=<输出单价>
```

未配置价格时界面明确显示“成本未配置”，不会把未知成本记为零。
