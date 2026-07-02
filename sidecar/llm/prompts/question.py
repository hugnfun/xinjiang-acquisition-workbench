def filter_prompt(comments: list[dict]) -> tuple[str, str]:
    items = "\n".join(f"{i+1}. {c['raw']}" for i, c in enumerate(comments))
    system = "你判断小红书评论哪些是用户在问问题或求助。只输出 JSON：{\"results\":[{\"raw\":str,\"is_question\":bool}]}。闲聊/陈述/夸赞不是问题。"
    user = f"判断以下评论是否为用户问题：\n{items}"
    return system, user

def normalize_prompt(questions: list[dict]) -> tuple[str, str]:
    items = "\n".join(f"{i+1}. {q['raw']}" for i, q in enumerate(questions))
    system = "把用户问题归一化：语义相同的合并成一个 normalized 文本（如\"几月去?\"和\"什么时候去\"都归一为\"最佳出行时间\"）。只输出 JSON：{\"results\":[{\"raw\":str,\"normalized\":str}]}。"
    user = f"归一化以下问题：\n{items}"
    return system, user

def name_prompt(samples: list[str]) -> tuple[str, str]:
    items = "\n".join(f"- {s}" for s in samples)
    system = "给一组用户问题起一个简短中文分类名（如\"季节·最佳时间\"）和一句描述。只输出 JSON：{\"name\":str,\"description\":str}。"
    user = f"这组问题：\n{items}\n\n起一个分类名和描述。"
    return system, user
