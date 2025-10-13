import os
import json
import re
import requests

# ========== 配置 ==========
DEEPSEEK_API_KEY = "your key"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
OUTPUT_DIR = "knowledge_base"

# ========== 读取 TXT ==========
def read_txt(file_path):
    """按行读取 TXT 并去掉空行"""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return lines

# ========== 调用 DeepSeek API 生成目录 ==========
def get_outline(text_chunk):
    """调用 DeepSeek 生成目录"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
你是知识库助手。请为以下内容生成一个精细的分层目录，并严格返回合法 JSON。
不要添加 ``` 或其他 Markdown 语法。
每个章节或小节对应的值可以是空数组。
内容如下：
{text_chunk}
"""
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"]

# ========== 清洗 JSON ==========
def clean_json(text):
    """去掉可能存在的 ```json 或 ``` 标记"""
    text = re.sub(r"^```json", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    return text.strip()

# ========== 按目录拆分内容 ==========
def split_content_by_outline(paragraphs, outline):
    """
    按照 outline 将 paragraphs 拆分到每个章节
    返回 content_map
    """
    content_map = {}

    keys = list(outline.keys())
    for idx, key in enumerate(keys):
        sub_outline = outline[key]

        # 查找匹配 key 的段落起始位置
        start_idx = None
        for i, para in enumerate(paragraphs):
            if key in para:
                start_idx = i
                break

        # 章节没有标题直接置空
        if start_idx is None:
            content_map[key] = {"文档": []}
            continue

        # 找到结束位置
        if idx + 1 < len(keys):
            # 下一个章节标题出现的段落索引
            end_idx = None
            next_key = keys[idx + 1]
            for j in range(start_idx + 1, len(paragraphs)):
                if next_key in paragraphs[j]:
                    end_idx = j
                    break
            if end_idx is None:
                end_idx = len(paragraphs)
        else:
            end_idx = len(paragraphs)

        chapter_paras = paragraphs[start_idx:end_idx]

        # 递归处理子章节
        if isinstance(sub_outline, dict) and sub_outline:
            content_map[key] = split_content_by_outline(chapter_paras, sub_outline)
        else:
            content_map[key] = {"文档": chapter_paras}

    return content_map

# ========== 保存成项目结构 JSON ==========
def save_project_structure(content_map, output_dir):
    """递归保存 content_map 为项目结构 JSON"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for chapter, sections in content_map.items():
        chapter_dir = os.path.join(output_dir, chapter.replace(" ", "_"))
        os.makedirs(chapter_dir, exist_ok=True)

        for section, paras in sections.items():
            filename = section.replace(" ", "_") + ".json"
            filepath = os.path.join(chapter_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({"title": section, "content": paras},
                          f, ensure_ascii=False, indent=2)

# ========== 主流程 ==========
if __name__ == "__main__":
    input_file = "sample.txt"  # 文本文件路径

    print("读取 TXT 文件...")
    paragraphs = read_txt(input_file)

    print("调用 DeepSeek 生成目录...")
    outline_text = get_outline("\n".join(paragraphs[:2000]))  # 文档太长可分块
    outline_text_clean = clean_json(outline_text)

    try:
        outline_dict = json.loads(outline_text_clean)
    except json.JSONDecodeError:
        print("目录不是合法 JSON，请检查模型输出：", outline_text_clean)
        exit(1)

    print("按照目录划分内容...")
    content_map = split_content_by_outline(paragraphs, outline_dict)

    print("生成项目结构 JSON 文件...")
    save_project_structure(content_map, OUTPUT_DIR)

    print(f"完成！结果存储在 {OUTPUT_DIR}/")
