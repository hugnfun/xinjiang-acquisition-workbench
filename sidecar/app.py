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
