import argparse
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 启动时加载项目根的 .env（DEEPSEEK_API_KEY 等密钥存这里，不进 git）
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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
