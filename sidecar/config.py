import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "data.db"
MEDIA_DIR = DATA_DIR / "media"
LOG_DIR = DATA_DIR / "logs"

def ensure_dirs():
    for d in (DATA_DIR, MEDIA_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)

# ── LLM provider 配置（env 驱动，可切换） ──
# 文本模型 (DeepSeek)
TEXT_MODEL = os.environ.get("TEXT_MODEL", "deepseek-v4-pro")
TEXT_API_BASE = os.environ.get("TEXT_API_BASE", "https://api.deepseek.com/v1")
TEXT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# 视觉模型 (本地 Ollama qwen-vl)
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen3-vl:8b")
VISION_API_BASE = os.environ.get("VISION_API_BASE", "http://localhost:11434/v1")
VISION_API_KEY = os.environ.get("VISION_API_KEY", "ollama")

# 视觉补标触发阈值：文本标签 confidence < 此值 → 看图补
VISION_TRIGGER_CONFIDENCE = float(os.environ.get("VISION_TRIGGER_CONFIDENCE", "0.6"))
VISION_MAX_IMAGES = int(os.environ.get("VISION_MAX_IMAGES", "1"))
