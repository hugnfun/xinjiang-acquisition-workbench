from sidecar.llm import labeling as L

def test_label_material_parses_tool_use(monkeypatch):
    fake_tool_input = {
        "labels": [
            {"dimension": "content_type", "value": "风景震撼", "confidence": 0.9},
            {"dimension": "season", "value": "秋", "confidence": 0.7},
        ]
    }
    block = type("B", (), {"type": "tool_use", "input": fake_tool_input})()
    class FakeResp:
        content = [block]
    class FakeClient:
        @property
        def messages(self):
            return self
        def create(self, **kw):
            return FakeResp()
    monkeypatch.setattr(L, "_get_client", lambda: FakeClient())
    result = L.label_material(
        title="赛里木湖", content="湖很蓝", image_paths=[],
        taxonomy=[{"name":"content_type","values":["风景震撼"]}],
    )
    assert len(result) == 2
    assert result[0]["value"] == "风景震撼"
    assert result[0]["confidence"] == 0.9
