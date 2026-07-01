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

import os
from pathlib import Path

def _fake_chat_client(json_text: str):
    """Mock an openai client: client.chat.completions.create(...) -> resp.choices[0].message.content"""
    class Resp:
        class Choice:
            class Msg:
                content = json_text
            message = Msg()
        choices = [Choice()]
    class Client:
        @property
        def chat(self): return self
        @property
        def completions(self): return self
        def create(self, **kw): return Resp()
    return Client()

def test_parse_labels_valid_json():
    text = '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.9,"out_of_taxonomy":false}]}'
    labels = L._parse_labels(text)
    assert len(labels) == 1
    assert labels[0]["value"] == "风景震撼"

def test_parse_labels_extracts_from_noise():
    text = '思考中...\n{"labels":[{"dimension":"route","value":"赛里木湖","confidence":0.8,"out_of_taxonomy":false}]}\n完毕'
    labels = L._parse_labels(text)
    assert len(labels) == 1
    assert labels[0]["value"] == "赛里木湖"

def test_parse_labels_invalid_returns_empty():
    assert L._parse_labels("not json at all") == []
    assert L._parse_labels("") == []

def test_label_with_text(monkeypatch):
    monkeypatch.setattr(L, "_get_text_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.9,"out_of_taxonomy":false}]}'
    ))
    result = L.label_with_text("赛里木湖", "湖很蓝", [{"name":"content_type","values":["风景震撼"]}])
    assert len(result) == 1
    assert result[0]["value"] == "风景震撼"
    assert result[0]["confidence"] == 0.9
    assert result[0]["source"] == "ai_text"

def test_label_with_vision(monkeypatch, tmp_path):
    # 造一张假图
    img = tmp_path / "t.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fake")
    monkeypatch.setattr(L, "_get_vision_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"route","value":"赛里木湖","confidence":0.85,"out_of_taxonomy":false}]}'
    ))
    result = L.label_with_vision(img, [{"name":"route","values":["赛里木湖"]}], focus_dims=["route"])
    assert len(result) == 1
    assert result[0]["value"] == "赛里木湖"
    assert result[0]["source"] == "ai_vision"

def test_merge_labels_dedup_keeps_higher_confidence():
    text_labels = [
        {"dimension":"route","value":"赛里木湖","confidence":0.5,"out_of_taxonomy":False,"source":"ai_text"},
    ]
    vision_labels = [
        {"dimension":"route","value":"赛里木湖","confidence":0.85,"out_of_taxonomy":False,"source":"ai_vision"},
        {"dimension":"content_type","value":"风景震撼","confidence":0.9,"out_of_taxonomy":False,"source":"ai_vision"},
    ]
    merged = L._merge_labels(text_labels, vision_labels)
    by_key = {(m["dimension"], m["value"]): m for m in merged}
    assert len(merged) == 2
    # 同 (route, 赛里木湖) 取高 confidence 的 vision 那条
    assert by_key[("route","赛里木湖")]["confidence"] == 0.85
    assert by_key[("route","赛里木湖")]["source"] == "ai_vision"
    assert by_key[("content_type","风景震撼")]["source"] == "ai_vision"
