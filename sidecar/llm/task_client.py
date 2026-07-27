import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.parse import urlparse
from openai import OpenAI
from sidecar import config
from sidecar.llm.prompts import question as qp, synthesis as sp


class UsageAccumulator:
    """聚合 OpenAI-compatible 响应中的 token usage，并估算人民币成本。"""

    def __init__(self, on_change=None):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.calls = 0
        self.usage_calls = 0
        self.unavailable_calls = 0
        self._on_change = on_change
        host = (urlparse(config.TASK_API_BASE).hostname or "").lower()
        self.is_local = host in {"localhost", "127.0.0.1", "::1"}
        self.provider = "ollama" if self.is_local else host or "unknown"
        self.model = config.TASK_MODEL
        self.input_price = config.TASK_INPUT_PRICE_CNY_PER_1M
        self.output_price = config.TASK_OUTPUT_PRICE_CNY_PER_1M

    def add_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int | None = None,
    ) -> None:
        prompt = max(0, int(prompt_tokens or 0))
        completion = max(0, int(completion_tokens or 0))
        total = max(0, int(total_tokens if total_tokens is not None else prompt + completion))
        self.calls += 1
        self.usage_calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += total
        self._notify()

    def add_response(self, response) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            self.calls += 1
            self.unavailable_calls += 1
            self._notify()
            return
        self.add_usage(
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
            getattr(usage, "total_tokens", None),
        )

    def to_dict(self) -> dict:
        cost: float | None
        if self.is_local:
            cost = 0.0
        elif self.input_price is not None and self.output_price is not None:
            cost = round(
                self.prompt_tokens * self.input_price / 1_000_000
                + self.completion_tokens * self.output_price / 1_000_000,
                8,
            )
        else:
            cost = None
        return {
            "available": self.usage_calls > 0,
            "calls": self.calls,
            "usage_calls": self.usage_calls,
            "unavailable_calls": self.unavailable_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_cny": cost,
            "provider": self.provider,
            "model": self.model,
        }

    def _notify(self) -> None:
        if self._on_change:
            self._on_change(self.to_dict())


_active_usage: ContextVar[UsageAccumulator | None] = ContextVar(
    "task_client_usage", default=None
)


@contextmanager
def track_usage(accumulator: UsageAccumulator):
    token = _active_usage.set(accumulator)
    try:
        yield accumulator
    finally:
        _active_usage.reset(token)

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

def chat_json(
    system: str, user: str, usage: UsageAccumulator | None = None
) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model=config.TASK_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    accumulator = usage or _active_usage.get()
    if accumulator:
        accumulator.add_response(resp)
    return resp.choices[0].message.content or ""

def filter_questions(
    comments: list[dict], usage: UsageAccumulator | None = None
) -> list[dict]:
    system, user = qp.filter_prompt(comments)
    return _parse_obj(chat_json(system, user, usage)).get("results", [])

def normalize_questions(
    questions: list[dict], usage: UsageAccumulator | None = None
) -> list[dict]:
    system, user = qp.normalize_prompt(questions)
    return _parse_obj(chat_json(system, user, usage)).get("results", [])

def name_cluster(
    samples: list[str], usage: UsageAccumulator | None = None
) -> dict:
    system, user = qp.name_prompt(samples)
    out = _parse_obj(chat_json(system, user, usage))
    return {"name": out.get("name", ""), "description": out.get("description", "")}

def synthesize(
    materials: list[dict], types: list[str], usage: UsageAccumulator | None = None
) -> dict:
    system, user = sp.synthesize_prompt(materials, types)
    out = _parse_obj(chat_json(system, user, usage))
    return {
        "selling_points": out.get("selling_points", []),
        "hooks": out.get("hooks", []),
        "ctas": out.get("ctas", []),
        "titles": out.get("titles", []),
    }
