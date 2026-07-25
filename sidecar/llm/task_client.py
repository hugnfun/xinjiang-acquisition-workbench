import json
import re
from openai import OpenAI
from sidecar import config
from sidecar.llm.prompts import question as qp, synthesis as sp

def _parse_obj(text: str) -> dict:
    """解析模型输出为顶层 dict。

    推理模型(MiniMax-M3)常在 JSON 前后输出思考/解释，且思考里可能带花括号；
    旧贪婪正则 \\{.*\\} 会把首个 { 到末个 } 误并成一坨 → json.loads 失败 → 返回 {}。
    顺序：去 markdown 围栏 → 整体 json.loads → 扫描所有「顶层平衡 {...}」逐个试
    (字符串内的 {/} 不计深度) → 兜底贪婪正则。返回第一个能解析的 dict。
    """
    if not text:
        return {}
    s = text.strip()
    # 去掉 markdown 代码围栏 ```json ... ``` / ``` ... ```
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9]*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
        s = s.strip()
    # 整体先试
    try:
        return json.loads(s)
    except Exception:
        pass
    # 扫描所有顶层平衡 {...} 候选，逐个尝试解析；
    # 推理里可能出现小的合法 JSON 片段(如 {"格式":"json"})，取最长的那个(真正的答案通常最大)。
    best: dict | None = None
    for cand in _extract_toplevel_json(s):
        try:
            obj = json.loads(cand)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if best is None or len(cand) > len(best[1]):
            best = (obj, cand)
    if best is not None:
        return best[0]
    # 兜底：旧贪婪正则
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}


def _extract_toplevel_json(s: str) -> list[str]:
    """抽出文本里所有顶层平衡的 {...} 子串（跳过 JSON 字符串内的 {/}）。"""
    out: list[str] = []
    depth = 0
    start: int | None = None
    in_str = False
    esc = False
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    out.append(s[start:i + 1])
                    start = None
    return out

def _get_client():
    return OpenAI(base_url=config.TASK_API_BASE, api_key=config.TASK_API_KEY, timeout=60, max_retries=1)

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
