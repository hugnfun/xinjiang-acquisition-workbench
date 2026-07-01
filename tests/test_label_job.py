from sidecar.llm import labeling as L
from pathlib import Path
import base64
from PIL import Image


def _real_image(path, fmt="JPEG"):
    """造一张真实可解码的图（Pillow 生成），避免假字节。"""
    Image.new("RGB", (8, 8), (10, 20, 30)).save(path, format=fmt)
    return path


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

def test_encode_image_block_converts_webp_to_jpeg(tmp_path):
    # 小红书下载的图常是 WebP 套 .jpg 后缀；Ollama 不支持 WebP，
    # _encode_image_block 必须把真实格式转成可加载的 JPEG（按字节判定，不信扩展名）。
    webp_file = tmp_path / "fake.jpg"  # 扩展名 jpg，内容 WebP
    Image.new("RGB", (8, 8), (10, 20, 30)).save(webp_file, format="WEBP")
    block = L._encode_image_block(webp_file)
    assert block["type"] == "image_url"
    url = block["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    # 解码出来的字节必须是真 JPEG（FF D8 FF），不是 WebP（RIFF）
    b64 = url.split("base64,", 1)[1]
    raw = base64.standard_b64decode(b64)
    assert raw[:3] == b"\xff\xd8\xff", f"expected JPEG magic FF D8 FF, got {raw[:4].hex()}"

def test_label_with_vision(monkeypatch, tmp_path):
    # 造一张真实可解码的图
    img = _real_image(tmp_path / "t.jpg")
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


# ── Task 3: label_material 串行编排 ──

def test_label_material_skips_vision_when_confident(monkeypatch):
    # 文本全高置信度 → 不触发视觉
    monkeypatch.setattr(L, "_get_text_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.9,"out_of_taxonomy":false}]}'
    ))
    called = {"vision": False}
    def boom(image_path, taxonomy, focus_dims=None):
        called["vision"] = True
        return []
    monkeypatch.setattr(L, "label_with_vision", boom)
    result = L.label_material("赛里木湖", "湖很蓝", [], [{"name":"content_type","values":["风景震撼"]}])
    assert called["vision"] is False
    assert len(result) == 1
    assert result[0]["source"] == "ai_text"

def test_label_material_triggers_vision_on_low_confidence(monkeypatch, tmp_path):
    img = _real_image(tmp_path / "t.jpg")
    # 文本有个低置信度标签 → 触发视觉，视觉补一条
    monkeypatch.setattr(L, "_get_text_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.4,"out_of_taxonomy":false}]}'
    ))
    monkeypatch.setattr(L, "_get_vision_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"route","value":"赛里木湖","confidence":0.85,"out_of_taxonomy":false}]}'
    ))
    result = L.label_material("赛里木湖", "湖很蓝", [img], [{"name":"content_type","values":["风景震撼"]},{"name":"route","values":["赛里木湖"]}])
    # 合并后 2 条：文本的风景震撼(0.4) + 视觉的赛里木湖(0.85)
    assert len(result) == 2
    sources = {r["source"] for r in result}
    assert sources == {"ai_text", "ai_vision"}

def test_label_material_vision_failure_degrades_gracefully(monkeypatch, tmp_path):
    img = tmp_path / "t.jpg"
    img.write_bytes(b"\xff\xd8fake")
    monkeypatch.setattr(L, "_get_text_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.4,"out_of_taxonomy":false}]}'
    ))
    def boom(image_path, taxonomy, focus_dims=None):
        raise RuntimeError("ollama down")
    monkeypatch.setattr(L, "label_with_vision", boom)
    result = L.label_material("赛里木湖", "湖很蓝", [img], [{"name":"content_type","values":["风景震撼"]}])
    # 视觉挂了 → 降级只用文本
    assert len(result) == 1
    assert result[0]["source"] == "ai_text"

def test_label_material_no_image_skips_vision(monkeypatch):
    # 低置信度但没有图 → 跳过视觉，仅返回文本标签
    monkeypatch.setattr(L, "_get_text_client", lambda: _fake_chat_client(
        '{"labels":[{"dimension":"content_type","value":"风景震撼","confidence":0.4,"out_of_taxonomy":false}]}'
    ))
    result = L.label_material("赛里木湖", "湖很蓝", [], [{"name":"content_type","values":["风景震撼"]}])
    assert len(result) == 1
    assert result[0]["source"] == "ai_text"
