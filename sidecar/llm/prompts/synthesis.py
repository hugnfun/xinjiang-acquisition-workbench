# 风格约束：压住 MiniMax 默认的套话倾向（实测无 few-shot 时必出
# "五感治愈/记一辈子"等空泛抒情）。要求每条带可感知的具体点。
_STYLE = """风格要求（重要，违反即作废重写）：
1. 具体细节 > 抽象抒情：每条必须带可感知的具体点——地名/季节/月份/数字(公里、天数、花费、海拔)/路况/体验细节，禁止空泛抒情。
2. 口语感、像真人在小红书发帖，不像广告文案。
3. 优先用素材标签里的差异化点当切入角度（如"16pro 原图直出""赛里木湖""独库公路""伊犁"），而不是泛泛而谈。
4. 每条独立可复用，互相不重复话术。

禁用套话（任何一条出现该输出即作废，必须用具体细节重写）：
五感治愈、记一辈子、此生必去、人间仙境、绝美风光、震撼心灵、美到窒息、洗涤灵魂、流连忘返、美如画，
以及任何"换个景点也能套"的空话。"""

# few-shot 正反例：告诉模型"好产出长啥样、坏产出长啥样"。
_EXAMPLES = """【正例参考】（具体、有信息量，照这个方向）：
- 卖点：赛里木湖 7 月冰蓝湖水，环湖一圈约 90km，手机原图直出不用调色
- 钩子：独库公路一年只开 4 个月，6 月底去正好赶上雪还没化完
- CTA：想要这份 10 天行程表的，评论区扣 1，我私信发你
- 标题：新疆 10 天不绕路路线｜伊犁+赛里木湖+独库，人均 4k

【反例】（套话，禁止这么写）：
- 卖点：五感治愈的体验，记一辈子的回忆 ✗
- 钩子：此生必去的人间仙境 ✗
- CTA：快来感受绝美风光吧 ✗"""


def synthesize_prompt(materials: list[dict], types: list[str]) -> tuple[str, str]:
    mats = "\n\n".join(f"【素材{i+1}】标题：{m['title']}\n正文：{m['content'][:300]}\n标签：{','.join(m.get('tags',[]))}" for i, m in enumerate(materials))
    want = []
    if "selling_point" in types: want.append("\"selling_points\":[卖点,...]")
    if "hook" in types: want.append("\"hooks\":[钩子,...]")
    if "cta" in types: want.append("\"ctas\":[行动号召,...]")
    if "title" in types: want.append("\"titles\":[标题,...]")
    system = (
        "你从小红书新疆旅游素材里提炼可用于内容创作的合成物。"
        "只输出 JSON，包含这些键（按需）："
        "{\"selling_points\":[...],\"hooks\":[...],\"ctas\":[...],\"titles\":[...]}。"
        "每类给3-5条，每条简短有力。\n\n"
        + _STYLE + "\n\n" + _EXAMPLES
    )
    user = f"从以下素材提炼（需要：{', '.join(want)}）：\n{mats}"
    return system, user
