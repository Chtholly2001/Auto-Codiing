# file: generate_project.py
import os
import json
import ast
import hashlib
import traceback
import re
import time
from typing import Dict, List, Any, Tuple, Optional

# 导入所有必要的提示词和工具
from ToDoList.config import OUTPUT_DIR
from ToDoList.prompts import PROJECT_PROMPT, REPAIR_PROMPT, DEBUG_PROMPT
from ToDoList.utils.api_client import call_deepseek
from ToDoList.utils.file_operations import parse_files_from_model, write_files, read_project_files, parse_files_from_model_with_continuation
from ToDoList.code_analyzer import CodeAnalyzer

# ------------------
# 新增：来自 chat.py 的截断续写实现（已适配为使用 call_deepseek）
# ------------------

# 配置：可以通过环境变量覆盖
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-coder")
API_TIMEOUT_SECONDS = int(os.environ.get("API_TIMEOUT_SECONDS", "600"))


class AutomationError(Exception):
    pass


def detect_relevant_files_with_model(bug_report: str, project_files: Dict[str, str]) -> List[str]:
    # 复用旧版 extract_relevant_content_with_ast 获取 files_dump
    files_dump = extract_relevant_content_with_ast(bug_report, project_files)

    DETECT_FILES_PROMPT = """你是一个 Python 全栈开发专家。请根据以下 bug 报告和项目文件内容，仅输出需要修改的文件路径（相对路径），每行一个，不要输出任何解释、代码或 markdown。

Bug 报告：
{bug}

项目文件内容：
{files_dump}

需要修改的文件：
"""
    prompt = DETECT_FILES_PROMPT.format(bug=bug_report, files_dump=files_dump)

    try:
        response = call_deepseek(prompt)
        # 提取每行非空、看起来像路径的字符串
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        paths = []
        for line in lines:
            # 过滤明显不是路径的内容（如中文、句子）
            if any(c in line for c in ['：', '。', '?', '!', '“', '”', '{', '}']):
                continue
            if '/' in line or '\\' in line or '.' in line:
                # 尝试标准化路径
                clean_path = line.split()[-1]  # 取最后一段（防编号）
                if any(clean_path.endswith(ext) for ext in ['.py', '.html', '.js', '.css', '.json', '.md', '.txt']):
                    paths.append(clean_path)
        return list(dict.fromkeys(paths))  # 去重保序
    except Exception as e:
        print(f"⚠️ 文件检测失败，回退到关键词扫描: {e}")
        # 回退：关键词匹配
        allow_ext = ('.py', '.html', '.js', '.css', '.json')
        phrases = re.findall(r'[\w\u4e00-\u9fa5]{2,}', bug_report)
        candidates = []
        for fp, content in project_files.items():
            if not any(fp.endswith(e) for e in allow_ext):
                continue
            if any(p in content for p in phrases):
                candidates.append(fp)
        return candidates if candidates else [k for k in project_files.keys() if any(k.endswith(e) for e in allow_ext)]


def remove_end_marker(code: str) -> str:
    """移除模型插入的结束标记 <!-- 文件结束，勿再生成 --> 及其前后可能的空白行"""
    marker = "<!-- 文件结束，勿再生成 -->"
    if marker in code:
        # 分割并取标记之前的部分
        code = code.split(marker, 1)[0]
        # 清理末尾可能残留的空行或注释
        lines = code.rstrip().splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        code = '\n'.join(lines)
    return code

def get_relevant_file_paths(bug_report: str, project_files: Dict[str, str]) -> List[str]:
    """
    完全复刻原版 extract_relevant_content_with_ast 的文件筛选逻辑，
    但仅返回被选中的文件路径列表（相对路径），不返回内容。
    """
    try:
        analyzer = CodeAnalyzer()
        # 尝试对每个 Python 文件做 AST 解析
        for file_path, content in project_files.items():
            if file_path.endswith('.py'):
                try:
                    analyzer.parse_with_ast(content, file_path)
                except Exception:
                    continue  # 单文件解析失败不中断

        # 使用 analyzer 查找与 bug_report 相关的元素
        try:
            relevant_elements = analyzer.find_relevant_elements(bug_report)
        except Exception:
            relevant_elements = []

        # 如果找到相关元素，则按文件分组，返回这些文件路径
        if relevant_elements:
            grouped: Dict[str, List[dict]] = {}
            for el in relevant_elements:
                fp = el.get('file_path', 'unknown.py')
                grouped.setdefault(fp, []).append(el)
            # 只保留项目中实际存在的文件
            return [fp for fp in grouped.keys() if fp in project_files]

        # 否则回退到全量 dump（但过滤掉大型二进制或不常见扩展）
        allow_ext = ('.py', '.md', '.txt', '.html', '.js', '.css', '.json')
        return [p for p, c in project_files.items() if any(p.endswith(e) for e in allow_ext)]

    except Exception as e:
        # 任何异常都回退到全量文本文件（与原版行为一致）
        allow_ext = ('.py', '.md', '.txt', '.html', '.js', '.css', '.json')
        return [p for p in project_files.keys() if any(p.endswith(e) for e in allow_ext)]

def extract_parameters_from_prompt(prompt: str) -> Tuple[str, str, str]:
    """
    从用户提示中解析截断提示文本。为了兼容旧流程，文件路径在外部传入时仍然有效。
    返回: (source_file, dest_file, truncation_hint)
    """
    # 默认占位（调用方可覆盖）
    source_file = "生成器/generated_project/app.py"
    dest_file = "生成器/generated_project/123.py"

    match_truncate = re.search(r"该文件被截断于 (.*?)。", prompt)
    truncation_hint = match_truncate.group(1).strip() if match_truncate else "文件的末尾。"

    print(f"[解析] 源文件: {source_file}, 目标文件: {dest_file}, 截断提示: {truncation_hint}")
    return source_file, dest_file, truncation_hint


def read_source_code(source_file: str) -> str:
    if not os.path.exists(source_file):
        raise AutomationError(f"源文件未找到: {source_file}")
    with open(source_file, 'r', encoding='utf-8') as f:
        return f.read()


def call_llm_for_continuation_via_call_deepseek(context_code: str, truncation_hint: str) -> str:
    """
    使用 call_deepseek(wrapper) 进行续写调用。该函数负责构建系统+用户提示并调用 call_deepseek。
    实现了简单的指数退避重试，但把实际HTTP细节交由 call_deepseek。
    返回：只包含续写代码的字符串（strip）。
    """
    system_instruction = (
        "你是一个专业的代码续写助手。请根据提供的上下文和截断提示，完成代码的续写。"
        "你的回复应该只包含新生成的代码部分，不要包含解释、markdown或原始上下文。"
    )

    user_prompt = (
        f"请续写以下代码片段。\n"
        f"上下文代码截断于此，下一行应该从 {truncation_hint} 描述的内容开始。\n"
        f"上下文代码：\n````\n{context_code.strip()}\n````"
    )

    full_prompt = system_instruction + "\n\n" + user_prompt

    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f"[LLM请求] 调用 call_deepseek (尝试 {attempt + 1})...")
            # call_deepseek 接受一个 prompt，返回模型原始文本
            raw = call_deepseek(full_prompt)
            if not raw or not raw.strip():
                raise AutomationError("LLM 返回为空内容。")
            return raw.strip()
        except Exception as e:
            print(f"调用失败: {e}")
            if attempt < max_retries - 1:
                delay = 2 ** (attempt + 1)
                print(f"等待 {delay}s 后重试...")
                time.sleep(delay)
            else:
                raise


def write_full_code_to_file(dest_file: str, source_code: str, continuation_code: str):
    full_code = source_code.strip() + "\n" + continuation_code.strip()
    os.makedirs(os.path.dirname(dest_file) or '.', exist_ok=True)
    with open(dest_file, 'w', encoding='utf-8') as f:
        f.write(full_code)
    print(f"写入完成: {dest_file} (长度 {len(full_code)})")


def run_code_continuation(user_prompt: str):
    """
    以单文件续写流程作为工具函数：解析 prompt -> 读文件 -> 请求续写 -> 写回。
    该函数在 project_generator 的某些模式中可被调用以替代复杂截断逻辑。
    """
    try:
        source_file, dest_file, truncation_hint = extract_parameters_from_prompt(user_prompt)
        source_code = read_source_code(source_file)
        continuation = call_llm_for_continuation_via_call_deepseek(source_code, truncation_hint)
        write_full_code_to_file(dest_file, source_code, continuation)
        print("run_code_continuation 完成。")
    except Exception as e:
        print(f"run_code_continuation 失败: {e}")


# ========== 从 聊天.py 移植的辅助函数 ==========
import ast
import re

def remove_triple_quotes(code: str) -> str:
    code = code.strip()
    if code.startswith('```'):
        code = code[3:].strip()
        if code.startswith('python'):
            code = code[6:].strip()
    if code.endswith('```'):
        code = code[:-3].strip()
    return code

def fix_code_indentation(code: str) -> str:
    lines = code.splitlines()
    fixed_lines = []
    for line in lines:
        stripped_line = line.strip()
        if fixed_lines and stripped_line.startswith("@app.route"):
            prev = fixed_lines[-1]
            if ("@app.route" in prev and (prev.count("(") > prev.count(")") or prev.count("'") % 2 == 1 or prev.count('"') % 2 == 1)):
                combined = (prev.strip() + stripped_line)
                combined = re.sub(r"/\s*\n\s*/", "/", combined)
                fixed_lines[-1] = combined
                continue
        if stripped_line:
            fixed_lines.append(line)
        else:
            if fixed_lines and fixed_lines[-1].strip():
                fixed_lines.append(line)
    while fixed_lines and not fixed_lines[0].strip():
        fixed_lines.pop(0)
    while fixed_lines and not fixed_lines[-1].strip():
        fixed_lines.pop()
    return "\n".join(fixed_lines)

def longest_overlap(a: str, b: str, min_len: int = 3) -> int:
    max_k = min(len(a), len(b))
    for k in range(max_k, min_len - 1, -1):
        if a.endswith(b[:k]):
            return k
    return 0

def validate_python(code: str):
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)

def repair_broken_string_join(a: str, b: str):
    single_open = a.count("'") % 2 == 1
    double_open = a.count('"') % 2 == 1
    joined = a + b
    if single_open or double_open:
        if single_open:
            joined = re.sub(r"(')(?s)([^']*)\n+([^']*)", lambda m: "'" + (m.group(2) + m.group(3)), joined)
        if double_open:
            joined = re.sub(r'(")(?s)([^"]*)\n+([^\"]*)', lambda m: '"' + (m.group(2) + m.group(3)), joined)
        if joined.count("'") % 2 == 0 and joined.count('"') % 2 == 0:
            return joined, True
    if re.search(r"/\s*\n\s*/", a + b):
        compact = re.sub(r"/\s*\n\s*/", "/", a + b)
        return compact, True
    return a + b, False

def smart_stitch(part_a: str, part_b: str, language: str = 'python'):
    info = {'method': None, 'overlap_len': 0, 'validated': False, 'error': None}
    k = longest_overlap(part_a, part_b, min_len=4)
    if k > 0:
        stitched = part_a + part_b[k:]
        info.update({'method': 'overlap', 'overlap_len': k})
    else:
        stitched, did_fix = repair_broken_string_join(part_a, part_b)
        if did_fix:
            info.update({'method': 'repair_string_or_url', 'overlap_len': 0})
        else:
            stitched = part_a + part_b
            info.update({'method': 'simple_concat', 'overlap_len': 0})
    if language.lower() == 'python':
        ok, err = validate_python(stitched)
        info['validated'] = ok
        info['error'] = err
        if not ok:
            lines = part_a.splitlines(keepends=True)
            for i in range(len(lines) - 1, -1, -1):
                candidate = ''.join(lines[:i + 1]) + part_b
                ok2, err2 = validate_python(candidate)
                if ok2:
                    info.update({'method': f'fallback_truncate_a_to_line_{i}', 'validated': True, 'error': None})
                    return candidate, info
    return stitched, info
# ===========================================


def create_new_file_from_bug_report(file_path: str, bug_report: str, project_files: Dict[str, str]) -> str:
    """
    根据 bug 报告创建一个全新文件。
    适用于模型建议新增文件的场景（如新增工具类、新路由等）。
    """
    # 构建上下文：提供现有项目结构供参考
    existing_files_summary = "\n".join([f"- {fp}" for fp in project_files.keys()])

    system_prompt = (
        "你是一个专业的全栈开发工程师。用户希望你根据需求创建一个全新的代码文件。\n"
        "请生成完整的、可直接运行的文件内容，不要包含任何解释、markdown或文件块标记。"
    )
    user_prompt = (
        f"请根据以下需求创建一个新文件：{file_path}\n\n"
        f"项目当前已有文件：\n{existing_files_summary}\n\n"
        f"具体需求描述：{bug_report}\n\n"
        "请输出该文件的完整代码内容（纯代码，无任何额外文本）："
    )

    raw_code = call_deepseek(system_prompt + "\n\n" + user_prompt).strip()
    # 清理可能的 markdown 包裹
    return remove_triple_quotes(raw_code)


def fix_single_file_like_chatpy(source_file: str, bug_report: str) -> str:
    """
    完全模仿 聊天.py 的提示词和两阶段流程，修复单个文件。
    返回完整的新代码字符串。
    """
    # 读取源码
    with open(source_file, 'r', encoding='utf-8') as f:
        source_code = f.read()

    # --- Step 1: 执行修改并生成前半部分 ---
    system1 = (
        "你是一个专业的代码修改助手。你将接收一个完整的源代码文件和一个修改需求。 "
        "你的任务是根据需求，在文件中执行修改，并生成**完整的、修改后的新文件**。 "
        "你的回复应该**只包含新生成的代码部分**，不要包含任何解释或Markdown格式。"
    )
    user1 = (
        f"请根据以下要求修改代码并开始生成完整的新文件，如果生成完整就在文件最底下写上`<!-- 文件结束，勿再生成 -->`，修改需求：{bug_report}\n"
        f"完整源代码：\n```\n{source_code.strip()}\n```"
    )
    part1 = call_deepseek(system1 + "\n\n" + user1).strip()

    if "<!-- 文件结束，勿再生成 -->" in part1:
        cleaned = remove_triple_quotes(part1)
        return remove_end_marker(cleaned)  # ← 第1处：清理结束标记


    # --- Step 2: 续写剩余部分（带完整上下文）---
    system2 = (
        "你是一个专业的代码续写和结构补全助手。你将接收所有必要的上下文信息：原始代码、原始需求和上次生成的代码片段。 "
        "你的任务是根据这些信息，从上次生成的代码末尾处开始，继续续写文件剩余的所有内容，直到文件结构完整。 "
        "你的回复应该**只包含新生成的代码部分**，不要包含任何解释或Markdown格式。"
    )
    user2 = (
        f"如果第一次生成的截断代码已经满足需求，或者已经生成到 `<!-- 文件结束，勿再生成 -->`，请**直接停止生成**，不要继续生成任何代码。否则，按照下述提示，继续生成剩余的代码：\n\n"
        f"以下是【原始源代码】（完整文件），仅用于参考文件结构：\n```ORIGINAL_SOURCE\n{source_code.strip()}\n```\n\n"
        f"以下是【第一次生成的被截断代码】。这是你上次工作的截止点：\n```PARTIAL_CODE\n{part1.strip()}\n```\n\n"
        f"原始修改需求是：【{bug_report}】\n\n"
        f"请根据此需求和原始源代码，从上一次生成的代码结尾处开始，继续生成剩余的代码，直到文件结构完整。**绝对不要重复已有的代码或任何解释**。"
    )
    part2 = call_deepseek(system2 + "\n\n" + user2).strip()

    # 拼接
    p1_clean = remove_triple_quotes(part1)
    p2_clean = remove_triple_quotes(part2) if part2.strip() else ""

    if not p2_clean:
        stitched = p1_clean
    else:
        stitched, _ = smart_stitch(p1_clean, p2_clean, language='python')
        stitched = fix_code_indentation(stitched)
    return remove_end_marker(stitched)  # ← 第2处：保险起见也清理一次




# ------------------
# 原有 generate_project.py 逻辑（保留并在需要处调用上面的续写函数）
# ------------------

# 生成项目的主流程
def extract_relevant_content_with_ast(bug_report: str, project_files: Dict[str, str]) -> str:
    try:
        analyzer = CodeAnalyzer()
        # 先尝试对每个 Python 文件做 AST 解析（解析失败不致命）
        for file_path, content in project_files.items():
            if file_path.endswith('.py'):
                try:
                    analyzer.parse_with_ast(content, file_path)
                except Exception:
                    # 单文件解析失败：记录但继续处理其他文件
                    continue

        # 使用 analyzer 查找与 bug_report 相关的元素（函数/类/route 等）
        try:
            relevant_elements = analyzer.find_relevant_elements(bug_report)
        except Exception:
            relevant_elements = []

        if relevant_elements:
            parts = []
            grouped: Dict[str, List[dict]] = {}
            for el in relevant_elements:
                fp = el.get('file_path', 'unknown.py')
                grouped.setdefault(fp, []).append(el)

            for fp, els in grouped.items():
                if fp in project_files:
                    full = project_files[fp]
                    lines = full.splitlines()
                    selected = set()
                    for el in els:
                        start = el.get('start_line', 1)
                        end = el.get('end_line', start)
                        for i in range(max(1, start - 2), min(len(lines) + 1, end + 3)):
                            selected.add(i)
                    sel_sorted = sorted(selected)
                    snippet = '\n'.join([lines[i - 1] for i in sel_sorted if 0 <= i - 1 < len(lines)])
                    parts.append(f"---FILE: {fp}\n{snippet}\n---END_FILE---")
                else:
                    for el in els:
                        parts.append(f"---FILE: {el.get('file_path','unknown.py')}\n{el.get('content','')}\n---END_FILE---")
            return '\n'.join(parts)

        # 回退到全量 dump（但过滤掉大型二进制或不常见扩展）
        allow_ext = ('.py', '.md', '.txt', '.html', '.js', '.css', '.json')
        all_parts = [f"---FILE: {p}\n{c}\n---END_FILE---" for p, c in project_files.items() if any(p.endswith(e) for e in allow_ext)]
        return '\n'.join(all_parts)
    except Exception as e:
        try:
            print(f"extract_relevant_content_with_ast 异常：{e}，退回全量文件提交。")
        except Exception:
            pass
        return '\n'.join([f"---FILE: {p}\n{c}\n---END_FILE---" for p, c in project_files.items()])


def generate_project_from_requirements(initial_requirements: str) -> None:
    prompt = PROJECT_PROMPT.format(requirements=initial_requirements)
    print("正在调用模型生成项目（首次）... 若模型未严格按格式输出，请根据提示重试。")
    raw = call_deepseek(prompt)
    files = parse_files_from_model(raw)
    if not files:
        print('\n未能从模型输出解析到文件块。模型原始返回如下（前400000字符）：\n')
        print(raw[:400000])
        return
    if 'README.md' in files:
        readme_content = files['README.md']
        missing_files = []
        if missing_files:
            print(f"警告：README.md 中描述的以下文件未实际生成：{missing_files}")
    write_files(files, OUTPUT_DIR)
    print(f"项目已生成到：{OUTPUT_DIR}\n")


def detect_files_to_delete(bug_report: str, existing_files: List[str]) -> List[str]:
    """
    根据 bug 报告检测需要删除的文件。
    返回应删除的文件路径列表（相对路径）。
    """
    DELETE_PROMPT = """你是一个 Python 全栈开发专家。请根据以下 bug 报告，判断是否需要删除某些文件。
如果需要删除，请仅输出要删除的文件路径（相对路径），每行一个。
如果不需要删除任何文件，请输出“无”。
不要输出任何解释、代码或 markdown。

Bug 报告：
{bug}

项目当前文件列表：
{file_list}

需要删除的文件："""

    file_list_str = "\n".join(f"- {fp}" for fp in existing_files)
    prompt = DELETE_PROMPT.format(bug=bug_report, file_list=file_list_str)

    try:
        response = call_deepseek(prompt)
        if "无" in response or not response.strip():
            return []

        lines = [line.strip() for line in response.split('\n') if line.strip()]
        delete_paths = []
        for line in lines:
            # 过滤非路径内容
            if any(c in line for c in ['：', '。', '?', '!', '“', '”', '{', '}']):
                continue
            if '/' in line or '\\' in line or '.' in line:
                clean_path = line.split()[-1]
                if any(clean_path.endswith(ext) for ext in ['.py', '.html', '.js', '.css', '.json', '.md', '.txt']):
                    delete_paths.append(clean_path)
        return list(dict.fromkeys(delete_paths))  # 去重保序
    except Exception as e:
        print(f"⚠️ 删除文件检测失败: {e}")
        return []


# 若干交互输入工具
def prompt_for_requirements() -> str:
    print('请输入需求（输入完毕后按 Enter，支持多行，单独一行输入 ".done" 结束输入）：')
    lines = []
    while True:
        try:
            line = input()
        except (KeyboardInterrupt, EOFError):
            print('\n输入终止，返回。')
            return ''
        if line.strip() == '.done':
            break
        lines.append(line)
    return '\n'.join(lines)




def prompt_for_bug_report() -> str:
    print('请输入bug报告（输入完毕后按 Enter，支持多行，单独一行输入 ".done" 结束输入）：')
    return prompt_for_requirements()


def prompt_for_debug_description() -> str:
    print('请输入debug描述（输入完毕后按 Enter，支持多行，单独一行输入 ".done" 结束输入）：')
    return prompt_for_requirements()


def prompt_for_confirmation(action_name: str) -> bool:
    print(f"确认执行 {action_name} 吗？(输入 .done 确认)")
    while True:
        try:
            line = input()
        except (KeyboardInterrupt, EOFError):
            print('\n操作取消。')
            return False
        if line.strip() == '.done':
            return True


def chat_with_model() -> None:
    print("进入对话模式（输入 .done 结束对话）：")
    conversation_history = []
    while True:
        try:
            user_input = input("你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print('\n退出对话模式。')
            break
        if user_input.lower() == '.done':
            print('退出对话模式。')
            break
        if not user_input:
            continue
        conversation_history.append({"role": "user", "content": user_input})
        try:
            prompt = ''
            for msg in conversation_history:
                if msg['role'] == 'user':
                    prompt += f"用户: {msg['content']}\n"
                else:
                    prompt += f"助手: {msg['content']}\n"
            response = call_deepseek(prompt)
            conversation_history.append({"role": "assistant", "content": response})
            print(f"模型: {response}\n")
        except Exception as e:
            print(f'对话时出错: {e}')


# 主交互循环：仅保留 generate / bug / debug / chat / info / show / exit

def repair_project_loop(initial_requirements: str = None) -> None:
    print("进入交互调试页面。可用命令：")
    print("  generate          —— 输入初始需求并生成项目（多行，结束输入用 .done，单次请求模型，提示词使用chat给出的简短需求描述）")
    print("  bug: <描述>        —— 提交 bug 报告并请求修复（可创建可修改文件，支持大文件截断继续生成）")
    print("  debug: <描述>      —— 只读诊断，返回调试指令与精确修改提示词（不修改文件）")
    print("  chat              —— 与 DeepSeek 模型进行对话,生成一段简短的需求描述")
    print("  info              —— 列出当前项目文件")
    print("  show <path>       —— 显示项目中文件内容（相对路径）")
    print("  exit              —— 退出程序")

    last_generated_requirements = initial_requirements

    while True:
        try:
            cmd = input('\n>> ').strip()
        except (KeyboardInterrupt, EOFError):
            print('\n收到退出信号，结束。')
            break
        if not cmd:
            continue
        if cmd.lower().startswith('exit'):
            if prompt_for_confirmation("退出程序"):
                print('退出交互模式。')
                break
            continue
        if cmd.lower() == 'chat':
            chat_with_model()
            continue
        if cmd.lower().startswith('info'):
            if prompt_for_confirmation("列出项目文件"):
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
                print(files[path][:20000])
            else:
                print(f"未找到文件：{path}")
            continue
        if cmd.lower() == 'generate':
            req = prompt_for_requirements()
            if not req:
                print('未输入需求或输入被取消。')
                continue
            last_generated_requirements = req
            try:
                generate_project_from_requirements(req)
            except Exception as e:
                print('生成项目失败：', e)
            continue

        # ------------------
        # 仅保留 BUG 修复逻辑（简化版）
        # ------------------
        if cmd.lower().startswith('bug:'):
            bug_report = cmd[len('bug:'):].strip()
            if not bug_report:
                bug_report = prompt_for_bug_report()  # ← 保留你的 .done 多行输入！
            if not bug_report:
                print('未输入bug报告或输入被取消。')
                continue

            files = read_project_files(OUTPUT_DIR)
            if not files:
                print('项目文件为空，请先运行 generate 命令生成项目。')
                continue

            # === 第一步：检测并删除文件（新增）===
            existing_file_list = list(files.keys())
            files_to_delete = detect_files_to_delete(bug_report, existing_file_list)
            for rel_path in files_to_delete:
                abs_path = os.path.join(OUTPUT_DIR, rel_path)
                if os.path.exists(abs_path):
                    try:
                        os.remove(abs_path)
                        print(f"🗑️ 成功删除文件: {rel_path}")
                        # 可选：从内存中移除，避免后续误操作
                        files.pop(rel_path, None)
                    except Exception as e:
                        print(f"❌ 删除失败 {rel_path}: {e}")
                        traceback.print_exc()
                else:
                    print(f"⚠️ 文件不存在，跳过删除: {rel_path}")

            # === 第二步：定位需修改/创建的文件（复用你原有的函数）===
            target_file_paths = detect_relevant_files_with_model(bug_report, files)
            if not target_file_paths:
                print("❌ 未能定位到任何需修改或创建的文件。")
                continue

            print(f"🔍 模型定位到 {len(target_file_paths)} 个需处理文件：")
            for fp in target_file_paths:
                print(f" - {fp}")

            # === 第三步：逐个处理（修复或创建）===
            for rel_path in target_file_paths:
                abs_path = os.path.join(OUTPUT_DIR, rel_path)
                if os.path.exists(abs_path):
                    # 修复现有文件
                    print(f"\n🔧 正在修复: {rel_path}")
                    try:
                        fixed_content = fix_single_file_like_chatpy(abs_path, bug_report)
                        with open(abs_path, 'w', encoding='utf-8') as f:
                            f.write(fixed_content)
                        print(f"✅ 成功修复: {rel_path}")
                    except Exception as e:
                        print(f"❌ 修复失败 {rel_path}: {e}")
                        traceback.print_exc()
                else:
                    # 创建新文件
                    print(f"\n🆕 正在创建: {rel_path}")
                    try:
                        new_content = create_new_file_from_bug_report(rel_path, bug_report, files)
                        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                        with open(abs_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        print(f"✅ 成功创建: {rel_path}")
                    except Exception as e:
                        print(f"❌ 创建失败 {rel_path}: {e}")
                        traceback.print_exc()
            continue
            continue


        if cmd.lower().startswith('debug:'):
            debug_desc = cmd[len('debug:'):].strip()
            if not debug_desc:
                debug_desc = prompt_for_debug_description()
                if not debug_desc:
                    print('未输入debug描述或输入被取消。')
                    continue
            files = read_project_files(OUTPUT_DIR)
            if not files:
                print('项目文件为空，请先运行 generate 命令生成项目。')
                continue
            files_dump = extract_relevant_content_with_ast(debug_desc, files)
            prompt = DEBUG_PROMPT.format(files_dump=files_dump, debug=debug_desc)
            print(f"正在调用模型进行只读诊断: {debug_desc[:50]}...")
            try:
                raw = call_deepseek(prompt)
                print('\n--- 诊断结果 ---\n')
                print(raw)
                print('\n--- 诊断结束 ---')
            except Exception as e:
                print('诊断失败：', e)
            continue

        print(f"未知命令: {cmd}")
        print("输入 'exit' 退出或输入 'info' 查看可用文件。")


if __name__ == '__main__':
    repair_project_loop()
