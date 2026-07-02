import json
import re
from openai import OpenAI
from sidecar import config
from sidecar.llm.prompts import question as qp, synthesis as sp

def _parse_obj(text: str) -> dict:
    """解析模型输出为顶层 dict。先 json.loads，失败正则提取首个 {...}。"""
    if not text:
        return {}
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}

def _get_client():
    return OpenAI(base_url=config.TASK_API_BASE, api_key=config.TASK_API_KEY)

def chat_json(system: str, user: str) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model=config.TASK_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content or ""

def filter_questions(comments: list[dict]) -> list[dict]:
    system, user = qp.filter_prompt(comments)
    return _parse_obj(chat_json(system, user)).get("results", [])

def normalize_questions(questions: list[dict]) -> list[dict]:
    system, user = qp.normalize_prompt(questions)
    return _parse_obj(chat_json(system, user)).get("results", [])

def name_cluster(samples: list[str]) -> dict:
    system, user = qp.name_prompt(samples)
    out = _parse_obj(chat_json(system, user))
    return {"name": out.get("name", ""), "description": out.get("description", "")}

def synthesize(materials: list[dict], types: list[str]) -> dict:
    system, user = sp.synthesize_prompt(materials, types)
    out = _parse_obj(chat_json(system, user))
    return {
        "selling_points": out.get("selling_points", []),
        "hooks": out.get("hooks", []),
        "ctas": out.get("ctas", []),
        "titles": out.get("titles", []),
    }
