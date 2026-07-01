import os
import base64
from pathlib import Path
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

def _get_client():
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

LABEL_TOOL = {
    "name": "record_labels",
    "description": "记录对一篇小红书笔记的标签判定结果",
    "input_schema": {
        "type": "object",
        "properties": {
            "labels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "dimension": {"type": "string"},
                        "value": {"type": "string"},
                        "confidence": {"type": "number"},
                        "out_of_taxonomy": {"type": "boolean"},
                    },
                    "required": ["dimension", "value", "confidence", "out_of_taxonomy"],
                },
            }
        },
        "required": ["labels"],
    },
}

def _build_system(taxonomy: list) -> str:
    lines = ["你是一个小红书新疆旅游内容标注助手。", "可用标签体系如下，只能从中选值；若都不合适，标记 out_of_taxonomy=true 并给出建议值。", ""]
    for dim in taxonomy:
        vals = "、".join(dim["values"])
        lines.append(f"维度 {dim['name']}（{dim.get('description','')}）: {vals}")
    lines.append("")
    lines.append("输出规则：每篇笔记给出至少 3 个标签；confidence 0~1；置信度<0.6 的也照给。")
    return "\n".join(lines)

def _encode_image(path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode()
    ext = path.suffix.lstrip(".").lower()
    media = "jpeg" if ext in ("jpg", "jpeg") else ext
    return {"type": "image", "source": {"type": "base64", "media_type": f"image/{media}", "data": data}}

def label_material(title: str, content: str, image_paths: list[Path], taxonomy: list) -> list:
    client = _get_client()
    system = _build_system(taxonomy)
    user_content = [{"type": "text", "text": f"标题：{title}\n\n正文：{content}"}]
    for p in image_paths[:3]:  # 最多 3 张图省 token
        p = Path(p)
        if p.exists():
            user_content.append(_encode_image(p))

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        tools=[LABEL_TOOL],
        tool_choice={"type": "tool", "name": "record_labels"},
        messages=[{"role": "user", "content": user_content}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input.get("labels", [])
    return []
