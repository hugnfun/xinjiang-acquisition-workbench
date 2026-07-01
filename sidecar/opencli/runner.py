import json
import re
import shutil
import subprocess
from pathlib import Path

OPENCLI_BIN = shutil.which("opencli") or "opencli"

def _extract_json(text: str):
    text = text.strip()
    m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
    if not m:
        raise ValueError(f"no JSON in opencli output: {text[:200]}")
    return json.loads(m.group(1))

def run_opencli(args: list[str], timeout: int = 180):
    cmd = [OPENCLI_BIN] + args
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"opencli failed: {' '.join(args)}\n{res.stderr[:500]}")
    return _extract_json(res.stdout)

def search(query: str, limit: int = 20):
    return run_opencli(["xiaohongshu", "search", query, "--limit", str(limit), "-f", "json"])

def note(url: str):
    return run_opencli(["xiaohongshu", "note", url, "-f", "json"], timeout=120)

def comments(url: str, limit: int = 50, with_replies: bool = True):
    args = ["xiaohongshu", "comments", url, "--limit", str(limit), "-f", "json"]
    if with_replies:
        args.append("--with-replies")
    return run_opencli(args, timeout=180)

def download(url: str, output: str):
    return run_opencli(["xiaohongshu", "download", url, "--output", output, "-f", "json"], timeout=300)
