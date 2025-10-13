# 知识库提问工程（DeepSeek + JSON 知识库）

## 1. 项目概述

本项目实现了一个基于 **DeepSeek** 的知识库问答系统，功能包括：

1. **从 TXT 文本生成结构化 JSON 知识库**

   * 利用 DeepSeek 自动生成精细目录
   * 按章节拆分文本内容
   * 保存为可递归的 JSON 项目结构

2. **对 JSON 知识库进行智能问答**

   * 加载整个知识库目录
   * 根据用户问题进行关键词匹配，选择最相关的章节
   * 将匹配内容和目录作为上下文传给 DeepSeek
   * 返回详细、准确的回答，并附带引用章节和 JSON 路径

项目特点：

* 精准回答问题：只读取最相关章节，避免无关信息干扰
* 可追溯性：答案带有章节和文件路径
* 可扩展性：支持多层目录和递归 JSON 内容

---

## 2. 项目结构

```
project/
├─ knowledge_base/           # 生成的 JSON 知识库目录
│  ├─ 章节1/
│  │  ├─ 小节1.json
│  │  └─ 小节2.json
│  └─ 章节2/
├─ sample.txt                # 原始文本输入
├─ generate_kb.py            # TXT → JSON 知识库脚本
├─ ask_kb.py                 # 问答主程序
└─ README.md
```

---

## 3. 功能模块

### 3.1 TXT → JSON 知识库 (`generate_kb.py`)

**流程：**

1. 读取 TXT 文本（按行去空行）
2. 调用 DeepSeek 生成精细目录（JSON 格式）
3. 清洗 DeepSeek 返回内容（去掉 \`\`\` 或非标准 JSON）
4. 按目录拆分段落，递归生成多层章节
5. 保存为 JSON 文件，目录结构与章节结构一致

**关键函数：**

* `read_txt(file_path)`：读取 TXT 内容
* `get_outline(text_chunk)`：调用 DeepSeek 生成目录
* `clean_json(text)`：清洗模型输出，保证合法 JSON
* `split_content_by_outline(paragraphs, outline)`：按目录拆分内容
* `save_project_structure(content_map, output_dir)`：保存为 JSON 项目结构

---

### 3.2 JSON 知识库问答 (`ask_kb.py`)

**流程：**

1. 遍历 `knowledge_base` 目录，加载 JSON 文件
2. 展开多层 `content`，生成：

   * `kb_index`：{章节名 → 段落列表}
   * `kb_dir`：知识库目录列表
3. 用户输入问题
4. `search_kb(question, kb_index)`：

   * 根据标题关键词匹配
   * 计算匹配分数
   * 取 Top N 最相关章节
5. `build_context_text(matches, kb_dir)`：

   * 构造上下文：目录 + 匹配内容
6. 调用 DeepSeek：

   * Prompt 指定“只用知识库内容回答”
   * 返回详细回答，并标注引用章节和 JSON 路径

**关键函数：**

* `flatten_content(content)`：递归展开多层 JSON 内容
* `load_knowledge_base_with_dir(root_dir)`：加载 JSON 知识库
* `search_kb(question, kb_index, top_n)`：关键词匹配检索
* `build_context_text(matches, kb_dir)`：构造上下文
* `ask_deepseek(question, kb_index, kb_dir)`：调用 DeepSeek API 生成答案

---

## 4. 配置说明

* `DEEPSEEK_API_KEY`：DeepSeek API Key
* `DEEPSEEK_API_URL`：DeepSeek API 接口地址
* `OUTPUT_DIR` / `KNOWLEDGE_BASE_DIR`：知识库 JSON 存储目录
* `TOP_N_MATCH`：关键词匹配时取最相关章节数量（默认 5）

---

## 5. 使用说明

### 5.1 生成知识库

```bash
python generate_kb.py
```

* 输入 TXT 文件 `sample.txt`
* 输出 JSON 知识库到 `knowledge_base/` 文件夹

### 5.2 知识库问答

```bash
python ask_kb.py
```

* 系统会加载知识库并等待输入问题
* 输入问题，系统返回答案，并附带引用章节和 JSON 文件路径
* 输入 `exit` 退出

---

## 6. 核心优势

1. **精准回答**

   * 关键词匹配+Top N 检索 → 模型只处理最相关内容

2. **可追溯**

   * 每条回答都标注来源章节和 JSON 文件

3. **灵活扩展**

   * 支持递归多层章节和大规模文档
   * 可替换关键词检索为向量检索提升语义匹配

4. **自动化**

   * TXT 文本直接生成结构化知识库
   * 深度集成 DeepSeek，实现端到端问答流程

---

## 7. 后续优化建议

* 使用 **嵌入 + 向量搜索** 替代简单关键词匹配，提高语义匹配准确率
* 支持 **多轮上下文对话**，保持用户问答连贯性
* 增加 **文档更新机制**，实现知识库动态更新

---

+-----------------+
|   sample.txt    |
|  原始文本文件   |
+--------+--------+
         |
         v
+-----------------------------+
|  generate_kb.py             |
|  TXT -> JSON 知识库         |
|  1. 读取 TXT                |
|  2. 调用 DeepSeek 生成目录  |
|  3. 清洗 JSON               |
|  4. 按目录拆分内容          |
|  5. 保存 JSON 项目结构      |
+--------+--------------------+
         |
         v
+-----------------------------+
|  knowledge_base/            |
|  结构化 JSON 知识库         |
|  章节/小节.json 文件         |
+--------+--------------------+
         |
         v
+-----------------------------+
|  ask_kb.py                  |
|  用户问答流程               |
|  1. 加载 JSON 知识库        |
|  2. 展开多层 content        |
|  3. 用户输入问题            |
|  4. search_kb 关键词匹配    |
|  5. Top N 相关章节选取     |
|  6. build_context_text 构造上下文 |
|  7. 调用 DeepSeek 返回答案  |
+--------+--------------------+
         |
         v
+-----------------------------+
| 用户看到答案                |
| 附带章节名和 JSON 文件路径  |
+-----------------------------+
