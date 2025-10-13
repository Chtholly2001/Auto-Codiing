# generate_project.py
import os
import re
import json
import requests
from typing import Dict

# ================= 配置 =================
# 推荐把 API KEY 放到环境变量 DEEPSEEK_API_KEY
DEEPSEEK_API_KEY = "your key"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
OUTPUT_DIR = "generated_project"

# =============== 正则与格式 ===============
# 模型和脚本之间约定的文件块格式
FILE_BLOCK_RE = re.compile(r"---FILE:\s*(?P<path>[^\n]+)\n(?P<content>.*?)\n---END_FILE---", re.DOTALL)

# =============== 辅助函数 ===============
def call_deepseek(prompt: str) -> str:
    """调用 DeepSeek，并在发生错误时提供调试信息。"""
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY.startswith("sk-REPLACE"):
        raise RuntimeError("未配置 DEEPSEEK_API_KEY。请在环境变量中设置 DEEPSEEK_API_KEY。")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=180)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"请求失败（网络/连接错误）：{e}")

    if resp.status_code == 401:
        body = resp.text[:2000]
        raise RuntimeError(
            "API 返回 401 Unauthorized。请检查 DEEPSEEK_API_KEY 是否正确。\n"
            f"请求 URL: {DEEPSEEK_API_URL}\n响应体（前2000字符）:\n{body}"
        )

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        body = resp.text[:2000]
        raise RuntimeError(f"HTTP 错误：{e}\n响应体（前2000字符）：\n{body}")

    # 尝试解析 JSON
    try:
        rj = resp.json()
    except ValueError:
        # 返回不是 JSON，直接返回文本供后续解析
        return resp.text

    # 兼容不同返回结构
    if isinstance(rj, dict) and "choices" in rj and isinstance(rj["choices"], list) and rj["choices"]:
        return rj["choices"][0].get("message", {}).get("content", "")
    if isinstance(rj, dict) and "result" in rj:
        return rj["result"]
    return json.dumps(rj, ensure_ascii=False)

def parse_files_from_model(text: str) -> Dict[str, str]:
    files: Dict[str, str] = {}
    for m in FILE_BLOCK_RE.finditer(text):
        path = m.group('path').strip()
        content = m.group('content')
        files[path] = content
    return files

def sanitize_path(p: str) -> str:
    if '..' in p or p.startswith('/') or p.startswith('\\'):
        raise ValueError(f"禁止使用上级或绝对路径：{p}")
    return p.replace('\\', '/').strip()

def write_files(files_map: Dict[str, str], base_dir: str):
    os.makedirs(base_dir, exist_ok=True)
    for path, content in files_map.items():
        sp = sanitize_path(path)
        full = os.path.join(base_dir, sp)
        d = os.path.dirname(full)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"写入：{full}")
        if full.endswith('.sh') or full.endswith('.py'):
            try:
                os.chmod(full, 0o755)
            except Exception:
                pass

def read_project_files(base_dir: str) -> Dict[str, str]:
    """返回项目目录下所有源码文件的相对路径->内容映射。"""
    data: Dict[str, str] = {}
    if not os.path.exists(base_dir):
        return data
    for root, _, files in os.walk(base_dir):
        for fn in files:
            # 读取常见文本文件（代码，md，txt，cfg）
            if any(fn.endswith(ext) for ext in ('.py', '.md', '.txt', '.cfg', '.ini', '.json', '.yml', '.yaml')):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, base_dir).replace('\\', '/')
                try:
                    with open(full, 'r', encoding='utf-8') as f:
                        data[rel] = f.read()
                except Exception as e:
                    data[rel] = f"<无法读取：{e}>"
    return data

# =============== 模型提示模板 ===============
PROJECT_PROMPT = '''\
你是资深 Python 工程师。下面是中文需求，请基于这些需求直接生成一个可运行的 Python 项目，严格只输出文件块：

---FILE: path/to/file.py
<文件内容>
---END_FILE---

必须包含 README.md 和启动脚本（run.sh 或 app 启动入口）。若有第三方依赖，请生成 requirements.txt。
不要输出任何额外说明或多余文本。

---需求开始---
{requirements}
---需求结束---
'''

REPAIR_PROMPT = '''\
你是资深 Python 工程师。下面是当前项目的文件列表（路径 -> 内容），以及一个用户提交的 bug 报告或改进请求。
请基于这些信息直接输出需要修改或新增的文件块，格式严格为：

---FILE: path/to/file.py
<完整文件内容，修改后的完整文件替换原文件>
---END_FILE---

要求：
1) 只输出确实需要修改或新增的文件块；其他文件不要输出。
2) 每个输出的文件必须为完整、可运行的 Python 源文件或文本文件（如 README.md）。
3) 如果修改涉及到第三方依赖，请同时在 requirements.txt 中更新依赖行。
4) 在回复前不要添加任何多余说明或注释（只输出文件块）。

---当前项目文件开始---
{files_dump}
---当前项目文件结束---

---用户 bug/需求开始---
{bug}
---用户 bug/需求结束---
'''

# =============== 交互循环 ===============
def generate_project_interactive(initial_requirements: str) -> None:
    prompt = PROJECT_PROMPT.format(requirements=initial_requirements)
    print("正在调用模型生成项目（首次）... 若模型未严格按格式输出，请根据提示重试。")
    raw = call_deepseek(prompt)
    files = parse_files_from_model(raw)
    if not files:
        print('\n未能从模型输出解析到文件块。模型原始返回如下（前4000字符）：\n')
        print(raw[:4000])
        return

    write_files(files, OUTPUT_DIR)
    print(f"项目已生成到：{OUTPUT_DIR}\n")

def repair_project_loop():
    print("进入交互调试模式。你可以输入：\n  bug: <问题描述>  —— 提交 bug 报告并请求修复\n  info             —— 列出当前项目文件\n  show <path>      —— 显示项目中文件内容（相对路径）\n  exit             —— 退出程序")

    while True:
        try:
            cmd = input('\n>> ').strip()
        except (KeyboardInterrupt, EOFError):
            print('\n收到退出信号，结束。')
            break

        if not cmd:
            continue

        if cmd.lower() == 'exit':
            print('退出交互模式。')
            break

        if cmd.lower() == 'info':
            files = read_project_files(OUTPUT_DIR)
            print(f"项目 ({OUTPUT_DIR}) 文件列表（共 {len(files)} 个可读文件）：")
            for p in sorted(files.keys()):
                print(' -', p)
            continue

        if cmd.startswith('show '):
            path = cmd[len('show '):].strip()
            files = read_project_files(OUTPUT_DIR)
            if path in files:
                print(f"--- {path} ---\n")
                print(files[path][:10000])
            else:
                print(f"未找到文件：{path}")
            continue

        if cmd.startswith('bug:') or cmd.startswith('bug '):
            bug_desc = cmd.split(':', 1)[1].strip() if ':' in cmd else cmd.split(' ', 1)[1].strip()
            if not bug_desc:
                print('请在 bug: 后提供问题描述。')
                continue

            print('收到 bug 报告，正在收集项目文件并请求模型生成修复...')
            files_map = read_project_files(OUTPUT_DIR)
            # 为防止过长，限制单文件内容长度
            files_dump = ''
            for p, c in files_map.items():
                files_dump += f'---PATH: {p}---\n'
                files_dump += (c[:4000] + '\n') if len(c) > 4000 else (c + '\n')

            prompt = REPAIR_PROMPT.format(files_dump=files_dump, bug=bug_desc)
            raw = call_deepseek(prompt)
            patched = parse_files_from_model(raw)
            if not patched:
                print('\n模型未按照文件块格式输出，原始返回（前4000字符）：\n')
                print(raw[:4000])
                continue

            print('模型建议修改/新增以下文件：')
            for p in patched.keys():
                print(' -', p)

            # 写入并覆盖
            write_files(patched, OUTPUT_DIR)
            print('修复已写入到项目目录。请运行测试或手动验证。')
            continue

        print('未知命令。可用命令：bug:, info, show <path>, exit')

def main_loop():
    print('启动：交互式项目生成与调试工具')
    print('请输入初始需求（输入完毕后按 Enter，支持多行，单独一行输入 \".done\" 结束输入）：')
    lines = []
    while True:
        try:
            line = input()
        except (KeyboardInterrupt, EOFError):
            print('\n输入终止，退出。')
            return
        if line.strip() == '.done':
            break
        lines.append(line)
    if not lines:
        print('未输入需求，退出。')
        return
    requirements_text = '\n'.join(lines)

    # 生成项目
    try:
        generate_project_interactive(requirements_text)
    except Exception as e:
        print('生成项目失败：', e)
        return

    # 进入修复/调试循环
    repair_project_loop()

if __name__ == '__main__':
    main_loop()
