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

# 云端文本任务计价（元 / 百万 token）。不提供时只记录 token，不伪造成本。
def _optional_float(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    return float(raw) if raw else None

TASK_INPUT_PRICE_CNY_PER_1M = _optional_float("TASK_INPUT_PRICE_CNY_PER_1M")
TASK_OUTPUT_PRICE_CNY_PER_1M = _optional_float("TASK_OUTPUT_PRICE_CNY_PER_1M")

# ── embedding（本地 qwen3-embedding，免费）──
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "qwen3-embedding:latest")
EMBEDDING_API_BASE = os.environ.get("EMBEDDING_API_BASE", "http://localhost:11434/v1")
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", "ollama")

# ── 聚类：余弦相似度阈值，>此值连通成簇 ──
# 不要轻易下调！聚类是连通分量(传递闭包: A~B 且 B~C 即同簇)，降阈值会链式合并：
# 实测 313 条 embedding 上 0.78→最大簇 58(合理)；0.72→最大簇 193(313 里过半挤一簇,
# 毫无意义)；0.68→265。且单问题簇占比始终 80-88% 不降——降阈值只让大簇越滚越大,
# 不合并单问题簇。0.78 是最大簇还合理的甜点。单问题簇多是算法+高维固有特性,
# 非阈值问题；要减单问题簇得换算法(LLM 语义合并/质心直径约束), 不是调这里。
CLUSTER_SIMILARITY_THRESHOLD = float(os.environ.get("CLUSTER_SIMILARITY_THRESHOLD", "0.78"))
