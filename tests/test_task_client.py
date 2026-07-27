from sidecar.llm import task_client as TC

def _fake_chat(text, usage=None):
    class Resp:
        class Choice:
            class Msg:
                content = text
            message = Msg()
        choices = [Choice()]
    Resp.usage = usage
    class Client:
        @property
        def chat(self): return self
        @property
        def completions(self): return self
        def create(self, **kw): return Resp()
    return Client()

def test_chat_json_returns_content(monkeypatch):
    monkeypatch.setattr(TC, "_get_client", lambda: _fake_chat("hello world"))
    assert TC.chat_json("sys", "usr") == "hello world"


def test_chat_json_collects_usage_and_cost(monkeypatch):
    class Usage:
        prompt_tokens = 120
        completion_tokens = 30
        total_tokens = 150

    monkeypatch.setattr(TC, "_get_client", lambda: _fake_chat("ok", Usage()))
    monkeypatch.setattr(TC.config, "TASK_API_BASE", "https://api.minimaxi.com/v1")
    monkeypatch.setattr(TC.config, "TASK_INPUT_PRICE_CNY_PER_1M", 2.0)
    monkeypatch.setattr(TC.config, "TASK_OUTPUT_PRICE_CNY_PER_1M", 8.0)
    usage = TC.UsageAccumulator()
    assert TC.chat_json("sys", "usr", usage) == "ok"
    snapshot = usage.to_dict()
    assert snapshot["available"] is True
    assert snapshot["prompt_tokens"] == 120
    assert snapshot["completion_tokens"] == 30
    assert snapshot["total_tokens"] == 150
    assert snapshot["cost_cny"] == 0.00048


def test_usage_missing_is_not_reported_as_zero_cost(monkeypatch):
    monkeypatch.setattr(TC, "_get_client", lambda: _fake_chat("ok"))
    monkeypatch.setattr(TC.config, "TASK_API_BASE", "https://api.minimaxi.com/v1")
    monkeypatch.setattr(TC.config, "TASK_INPUT_PRICE_CNY_PER_1M", None)
    monkeypatch.setattr(TC.config, "TASK_OUTPUT_PRICE_CNY_PER_1M", None)
    usage = TC.UsageAccumulator()
    with TC.track_usage(usage):
        assert TC.chat_json("sys", "usr") == "ok"
    snapshot = usage.to_dict()
    assert snapshot["available"] is False
    assert snapshot["unavailable_calls"] == 1
    assert snapshot["cost_cny"] is None

def test_filter_questions_parses(monkeypatch):
    monkeypatch.setattr(TC, "_get_client", lambda: _fake_chat(
        '{"results":[{"raw":"几月去","is_question":true},{"raw":"好的","is_question":false}]}'
    ))
    out = TC.filter_questions([{"raw":"几月去"}, {"raw":"好的"}])
    assert len(out) == 2
    assert out[0]["is_question"] is True
    assert out[1]["is_question"] is False

def test_normalize_questions_parses(monkeypatch):
    monkeypatch.setattr(TC, "_get_client", lambda: _fake_chat(
        '{"results":[{"raw":"几月去?","normalized":"最佳出行时间"},{"raw":"什么时候去","normalized":"最佳出行时间"}]}'
    ))
    out = TC.normalize_questions([{"raw":"几月去?"}, {"raw":"什么时候去"}])
    assert out[0]["normalized"] == "最佳出行时间"
    assert out[1]["normalized"] == "最佳出行时间"

def test_name_cluster_parses(monkeypatch):
    monkeypatch.setattr(TC, "_get_client", lambda: _fake_chat(
        '{"name":"季节·最佳时间","description":"用户问什么时候去新疆最好"}'
    ))
    out = TC.name_cluster(["几月去", "什么时候去", "几月份最好"])
    assert out["name"] == "季节·最佳时间"
    assert "最好" in out["description"]

def test_synthesize_parses(monkeypatch):
    monkeypatch.setattr(TC, "_get_client", lambda: _fake_chat(
        '{"selling_points":["纯玩无购物","六年零差评"],"hooks":["人生必去一次"],"ctas":["私信定制"],"titles":["新疆10日攻略"]}'
    ))
    out = TC.synthesize([{"title":"t","content":"c","tags":["风景震撼"]}], ["selling_point","hook","cta","title"])
    assert out["selling_points"] == ["纯玩无购物","六年零差评"]
    assert out["hooks"] == ["人生必去一次"]


def test_parse_obj_markdown_fenced():
    """MiniMax 常把 JSON 包在 ```json 围栏里。"""
    out = TC._parse_obj('```json\n{"name":"x","results":[{"a":1}]}\n```')
    assert out == {"name": "x", "results": [{"a": 1}]}


def test_parse_obj_reasoning_prefix():
    """推理模型在 JSON 前输出思考（含花括号），不能把首尾 { } 误并。"""
    raw = '让我想想。用户要卖点。注意 {"格式":"json"}。\n{"selling_points":["具体卖点"],"hooks":["钩子"]}'
    out = TC._parse_obj(raw)
    assert out["selling_points"] == ["具体卖点"]
    assert out["hooks"] == ["钩子"]


def test_parse_obj_stray_braces_then_json():
    """思考里有多个花括号片段，仍能定位真正的 JSON 对象。"""
    raw = '分析 {候选1} 和 {候选2} 后，输出如下：\n```json\n{"titles":["t1"]}\n```'
    out = TC._parse_obj(raw)
    assert out == {"titles": ["t1"]}


def test_parse_obj_brace_inside_string():
    """JSON 字符串值里含 {/}，不能破坏平衡计数。"""
    out = TC._parse_obj('{"ctas":["点 {这里} 领取","扣1"]}')
    assert out["ctas"] == ["点 {这里} 领取", "扣1"]


def test_parse_obj_empty_and_garbage():
    assert TC._parse_obj("") == {}
    assert TC._parse_obj("   ") == {}
    assert TC._parse_obj("没有json的东西") == {}
