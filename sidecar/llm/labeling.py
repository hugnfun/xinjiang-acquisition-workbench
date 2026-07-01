import base64
import json
import re
from pathlib import Path
from openai import OpenAI
from sidecar import config


def _parse_labels(text: str) -> list:
    """从模型输出解析标签列表。先 json.loads，失败则正则提取首个 JSON 对象。"""
    if not text:
        return []
    text = text.strip()
    try:
        obj = json.loads(text)
        return obj.get("labels", [])
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        obj = json.loads(m.group(0))
        return obj.get("labels", [])
    except Exception:
        return []


def _get_text_client():
    if not config.TEXT_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置")
    return OpenAI(base_url=config.TEXT_API_BASE, api_key=config.TEXT_API_KEY)


def _get_vision_client():
    return OpenAI(base_url=config.VISION_API_BASE, api_key=config.VISION_API_KEY)


def _build_taxonomy_prompt(taxonomy: list, focus_dims=None) -> str:
    lines = ["可用标签体系如下，只能从中选值；若都不合适，标记 out_of_taxonomy=true 并给出建议值。", ""]
    for dim in taxonomy:
        vals = "、".join(dim["values"])
        lines.append(f"维度 {dim['name']}（{dim.get('description','')}）: {vals}")
    lines.append("")
    if focus_dims:
        lines.append(f"请重点针对以下维度判断：{'、'.join(focus_dims)}")
    lines.append("输出规则：只输出 JSON，格式 {\"labels\":[{\"dimension\":str,\"value\":str,\"confidence\":float(0-1),\"out_of_taxonomy\":bool}]}；给出至少 1 个标签。")
    return "\n".join(lines)


def label_with_text(title: str, content: str, taxonomy: list) -> list:
    """DeepSeek 文本打标（JSON mode）。返回标签，每条带 source='ai_text'。"""
    client = _get_text_client()
    system = "你是一个小红书新疆旅游内容标注助手。" + _build_taxonomy_prompt(taxonomy)
    resp = client.chat.completions.create(
        model=config.TEXT_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"标题：{title}\n\n正文：{content}"},
        ],
    )
    text = resp.choices[0].message.content or ""
    labels = _parse_labels(text)
    for lb in labels:
        lb["source"] = "ai_text"
    return labels


def _encode_image_block(path) -> dict:
    """读图并用 Pillow 转成真 JPEG 再 base64。

    小红书下载的图常是 WebP 套 .jpg 后缀，而 Ollama 不支持 WebP
    （实测 0.30.7 + qwen3-vl:8b 喂 WebP 直接 400 "Failed to load image"）。
    不能按扩展名声明 media_type——必须按真实字节转成可加载的 JPEG。
    """
    import io
    from PIL import Image
    img = Image.open(path)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG")
    data = base64.standard_b64encode(buf.getvalue()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}


def label_with_vision(image_path, taxonomy: list, focus_dims=None) -> list:
    """本地 qwen-vl 看图打标。返回标签，每条带 source='ai_vision'。"""
    client = _get_vision_client()
    system = "你看一张小红书新疆旅游笔记的图片，判断内容标签。" + _build_taxonomy_prompt(taxonomy, focus_dims)
    user_content = [
        {"type": "text", "text": "请根据图片判断标签，只输出 JSON。"},
        _encode_image_block(image_path),
    ]
    resp = client.chat.completions.create(
        model=config.VISION_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    text = resp.choices[0].message.content or ""
    labels = _parse_labels(text)
    for lb in labels:
        lb["source"] = "ai_vision"
    return labels


def _merge_labels(text_labels: list, vision_labels: list) -> list:
    """合并两路标签，按 (dimension,value) 去重，保留 confidence 更高（及其 source）的那条。"""
    merged = {}
    for lb in text_labels + vision_labels:
        key = (lb.get("dimension"), lb.get("value"))
        if key not in merged:
            merged[key] = lb
        elif lb.get("confidence", 0) > merged[key].get("confidence", 0):
            merged[key] = lb
    return list(merged.values())


def label_material(title: str, content: str, image_paths: list, taxonomy: list) -> list:
    """串行编排：DeepSeek 文本打标 → 低置信度触发 qwen-vl 看图补 → 合并去重。"""
    text_labels = label_with_text(title, content, taxonomy)

    low_conf = [lb for lb in text_labels if lb.get("confidence", 0) < config.VISION_TRIGGER_CONFIDENCE]
    imgs = [Path(p) for p in image_paths[:config.VISION_MAX_IMAGES] if Path(p).exists()]
    if not low_conf or not imgs:
        return text_labels

    focus_dims = list({lb["dimension"] for lb in low_conf})
    try:
        vision_labels = label_with_vision(imgs[0], taxonomy, focus_dims=focus_dims)
    except Exception:
        # 视觉降级：仅用文本标签
        return text_labels
    return _merge_labels(text_labels, vision_labels)
