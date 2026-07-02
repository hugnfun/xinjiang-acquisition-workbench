import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 启动时加载项目根的 .env（DEEPSEEK_API_KEY 等密钥存这里，不进 git）
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 关键：让本地调用（ollama @ localhost:11434）绕过系统代理。
# 这台机器有 Clash 代理 (http_proxy/https_proxy=127.0.0.1:7890)，openai SDK 用的
# httpx 默认读这些 env，会把连 ollama 的请求也发给 Clash → 卡死（问题池 job 因此挂起）。
# 外网调用（DeepSeek）仍走代理；localhost/127.0.0.1 绕过。
_no_proxy = os.environ.get("NO_PROXY", "")
_extras = {"localhost", "127.0.0.1", "::1"}
existing = {x.strip() for x in _no_proxy.split(",") if x.strip()}
missing = _extras - existing
if missing:
    os.environ["NO_PROXY"] = (_no_proxy + "," if _no_proxy else "") + ",".join(sorted(_extras | missing))
    os.environ["no_proxy"] = os.environ["NO_PROXY"]  # httpx 也读小写

def create_app() -> FastAPI:
    app = FastAPI(title="workbench-sidecar")
    # CORS: Tauri webview 页面源是 tauri://localhost (prod) 或 http://localhost:1420
    # (vite dev)，fetch http://127.0.0.1:<port> 是跨域。本地工具，放开所有源。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    @app.get("/health")
    def health():
        return {"ok": True}
    from sidecar.api import materials, tags, jobs, questions, synthesis
    app.include_router(materials.router)
    app.include_router(tags.router)
    app.include_router(jobs.router)
    app.include_router(questions.router)
    app.include_router(synthesis.router)
    # 启动时清理僵尸 job：sidecar 重启后，之前 running/queued 的 job 永远不会
    # 完成（执行它们的进程已死），会把前端的"防重"逻辑卡死（按钮一直禁用）。
    # 统一标记为 failed。
    try:
        from sidecar.db.session import get_session, init_db
        from sidecar.db.models import ScrapeJob
        init_db()
        s = get_session()
        zombies = s.query(ScrapeJob).filter(ScrapeJob.status.in_(["running", "queued"])).all()
        for j in zombies:
            j.status = "failed"
            j.error = "僵尸任务清理：sidecar 重启时未正常结束"
        if zombies:
            s.commit()
            print(f"[startup] 清理 {len(zombies)} 个僵尸 job", flush=True)
    except Exception as e:
        print(f"[startup] 僵尸清理失败（非致命）: {e}", flush=True)
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
