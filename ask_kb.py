import os
import json
import requests

# ========== 配置 ==========
DEEPSEEK_API_KEY = "your key"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
KNOWLEDGE_BASE_DIR = "knowledge_base"
TOP_N_MATCH = 5  # 匹配分数前N的章节内容

# ========== 辅助函数 ==========
def flatten_content(content):
    """
    递归展开多层 dict 中的列表
    """
    flat = []
    if isinstance(content, list):
        flat.extend(content)
    elif isinstance(content, dict):
        for v in content.values():
            flat.extend(flatten_content(v))
    return flat

# ========== 加载知识库并生成目录 ==========
def load_knowledge_base_with_dir(root_dir):
    """
    遍历知识库 JSON 文件
    返回：
        kb_index: {章节名 -> 段落列表}
        kb_dir: 列表，存储章节目录
    """
    kb_index = {}
    kb_dir = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith(".json"):
                path = os.path.join(dirpath, fname)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    title = data.get("title", fname)
                    content = data.get("content", [])
                    # 递归展开多层 content
                    content = flatten_content(content)
                    kb_index[title] = content
                    # 目录记录路径 + title
                    relative_path = os.path.relpath(path, root_dir).replace("\\", "/")
                    kb_dir.append(f"{relative_path}: {title}")
    return kb_index, kb_dir

# ========== 简单关键词匹配 ==========
def search_kb(question, kb_index, top_n=TOP_N_MATCH):
    """
    根据问题匹配相关章节
    返回 [(title, 段落列表)]
    """
    matches = []
    for title, paras in kb_index.items():
        score = sum(question.count(word) for word in title.split())
        if score > 0:
            matches.append((score, title, paras))
    matches.sort(reverse=True)
    return [(title, paras) for score, title, paras in matches[:top_n]]

# ========== 构造上下文 ==========
def build_context_text(matches, kb_dir):
    """
    构造给 DeepSeek 的上下文，包含目录和匹配内容
    """
    context_text = "知识库目录：\n" + "\n".join(kb_dir) + "\n\n"
    for title, paras in matches:
        context_text += f"\n章节: {title}\n" + "\n".join(paras) + "\n"
    return context_text

# ========== 调用 DeepSeek ==========
def ask_deepseek(question, kb_index, kb_dir):
    matches = search_kb(question, kb_index)
    context_text = build_context_text(matches, kb_dir)

    prompt = f"""
你是知识库助手，请根据以下知识库内容回答用户问题，
最好不要使用 DeepSeek 自己的知识回答问题，
知识库内没有提问的知识就回答没有，
如果知识库内没有提问的知识，而且用户要求回答知识库外的内容，请标明知识库内没有目标内容，明确标明使用了DeepSeek 模型，进行回答。
请使用 JSON 格式返回，格式如下
：
知识内容：
{context_text}

用户问题：
{question}

请给出详细、准确的回答，并在回答中注明引用的章节名和 JSON 文件路径。
"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    result = response.json()
    answer = result["choices"][0]["message"]["content"]
    return answer

# ========== 主流程 ==========
if __name__ == "__main__":
    print("加载知识库...")
    kb_index, kb_dir = load_knowledge_base_with_dir(KNOWLEDGE_BASE_DIR)
    print(f"知识库加载完成，共 {len(kb_index)} 个章节")

    while True:
        question = input("请输入问题（exit退出）：")
        if question.lower() == "exit":
            break

        answer = ask_deepseek(question, kb_index, kb_dir)
        print("\n==== 回答 ====\n")
        print(answer)
        print("\n================\n")
