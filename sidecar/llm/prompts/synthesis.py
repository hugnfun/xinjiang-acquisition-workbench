def synthesize_prompt(materials: list[dict], types: list[str]) -> tuple[str, str]:
    mats = "\n\n".join(f"【素材{i+1}】标题：{m['title']}\n正文：{m['content'][:300]}\n标签：{','.join(m.get('tags',[]))}" for i, m in enumerate(materials))
    want = []
    if "selling_point" in types: want.append("\"selling_points\":[卖点,...]")
    if "hook" in types: want.append("\"hooks\":[钩子,...]")
    if "cta" in types: want.append("\"ctas\":[行动号召,...]")
    if "title" in types: want.append("\"titles\":[标题,...]")
    system = "你从小红书新疆旅游素材里提炼可用于内容创作的合成物。只输出 JSON，包含这些键（按需）：{\"selling_points\":[...],\"hooks\":[...],\"ctas\":[...],\"titles\":[...]}。每类给3-5条，简短有力。"
    user = f"从以下素材提炼（需要：{', '.join(want)}）：\n{mats}"
    return system, user
