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

# ── 通用文本任务 provider（问题过滤/归一化/命名/合成提炼）──
# 优先级：MINIMAX_API_KEY 设了 → 用 MiniMax；否则回退本地 Ollama 27b。
# 本地 27b 每条评论 ~20s，1637 条要 8+ 小时不实用，故默认走云端 MiniMax。
_minimax_key = os.environ.get("MINIMAX_API_KEY", "")
if _minimax_key:
    TASK_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-Text-01")
    TASK_API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
    TASK_API_KEY = _minimax_key
else:
    TASK_MODEL = os.environ.get("TASK_MODEL", "qwen3.6:27b-q4_K_M")
    TASK_API_BASE = os.environ.get("TASK_API_BASE", "http://localhost:11434/v1")
    TASK_API_KEY = os.environ.get("TASK_API_KEY", "ollama")

# ── embedding（本地 qwen3-embedding，免费）──
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "qwen3-embedding:latest")
EMBEDDING_API_BASE = os.environ.get("EMBEDDING_API_BASE", "http://localhost:11434/v1")
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", "ollama")

# ── 聚类：余弦相似度阈值，>此值连通成簇 ──
CLUSTER_SIMILARITY_THRESHOLD = float(os.environ.get("CLUSTER_SIMILARITY_THRESHOLD", "0.78"))
