from sidecar.llm import task_client as TC

def _fake_chat(text):
    class Resp:
        class Choice:
            class Msg:
                content = text
            message = Msg()
        choices = [Choice()]
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
