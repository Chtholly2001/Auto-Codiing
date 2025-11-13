import re
import os
import json
import requests
import time
import ast
from typing import Tuple, Optional

# --- 配置您的 API 密钥、模型和 DeepSeek Endpoint ---
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-6572f61cfd644e039072109240b19529")
API_BASE_URL = "https://api.deepseek.com/v1"
API_URL = f"{API_BASE_URL}/chat/completions"
DEEPSEEK_MODEL = "deepseek-coder"

API_TIMEOUT_SECONDS = 600
# --- 硬编码文件路径 ---
HARDCODED_SOURCE_FILE = "生成器/generated_project/app.py"  # 源代码输入文件
HARDCODED_DEST_FILE = "生成器/generated_project/123.py"  # 完整代码输出文件
# ---------------------------------------

class AutomationError(Exception):
    """自定义自动化错误"""
    pass


def remove_triple_quotes(code: str) -> str:
    """
    Remove extra triple quotes and code block markers from the code.
    """
    code = code.strip()
    # 更健壮地处理代码块标记（支持带空格或小写python的情况）
    if code.startswith('```'):
        # 移除开头的```标记（无论是否带python）
        code = code[3:].strip()
        # 如果开头是python相关标识，继续移除
        if code.startswith('python'):
            code = code[6:].strip()
    # 移除结尾的```标记
    if code.endswith('```'):
        code = code[:-3].strip()
    return code


def fix_code_indentation(code: str) -> str:
    """
    修复代码中的拼接问题和格式错误，特别是处理换行和语法错误
    """
    lines = code.splitlines()
    fixed_lines = []
    for line in lines:
        stripped_line = line.strip()
        # 修复路由路径被拆分到两行的问题（使用双引号避免单引号冲突）
        # 更通用的检查：如果上一行以 @app.route 开头但不包含右括号/引号关闭，则尝试合并
        if fixed_lines and stripped_line.startswith("@app.route"):
            # 如果上一行看起来像是被截断的 route 起始（例如以 '/cart 开头但没有结束的引号）
            prev = fixed_lines[-1]
            if ("@app.route" in prev and (prev.count("(") > prev.count(")") or prev.count("'") % 2 == 1 or prev.count('"') % 2 == 1)):
                # 合并上一行和当前行并替换为单行定义（保守处理）
                combined = (prev.strip() + stripped_line)
                # 规范化连续斜杠分行问题： e.g. '/cart\n/update' -> '/cart/update'
                combined = re.sub(r"/\s*\n\s*/", "/", combined)
                fixed_lines[-1] = combined
                continue
        # 去除多余的空行但保留必要的空行
        if stripped_line:
            fixed_lines.append(line)
        else:
            # 只保留有内容行之间的单个空行
            if fixed_lines and fixed_lines[-1].strip():
                fixed_lines.append(line)
    # 去除首尾空行
    while fixed_lines and not fixed_lines[0].strip():
        fixed_lines.pop(0)
    while fixed_lines and not fixed_lines[-1].strip():
        fixed_lines.pop()
    return "\n".join(fixed_lines)


# ----------------- 智能拼接模块 -----------------

def longest_overlap(a: str, b: str, min_len: int = 3) -> int:
    """返回 a 的尾部和 b 的头部最长相等重叠长度（至少 min_len），否则 0。"""
    max_k = min(len(a), len(b))
    for k in range(max_k, min_len - 1, -1):
        if a.endswith(b[:k]):
            return k
    return 0


def validate_python(code: str) -> Tuple[bool, Optional[str]]:
    """尝试 ast.parse，返回 (ok, error_message_or_None)."""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)


def repair_broken_string_join(a: str, b: str) -> Tuple[str, bool]:
    """
    处理像 '/cart\n\n/update' 这种字符串中被换行分成两段的情况。
    如果检测到单引号或双引号包裹的部分被断开，会尝试把中间换行移除。
    返回 (maybe_fixed_text, did_fix_flag)
    """
    # 判断 a 是否在引号中未闭合（粗略判断）
    single_open = a.count("'") % 2 == 1
    double_open = a.count('"') % 2 == 1
    joined = a + b
    if single_open or double_open:
        # 把引号内的换行删除（谨慎处理，只在简单场景中使用）
        if single_open:
            joined = re.sub(r"(')(?s)([^']*)\n+([^']*)", lambda m: "'" + (m.group(2) + m.group(3)), joined)
        if double_open:
            joined = re.sub(r'(")(?s)([^"]*)\n+([^\"]*)', lambda m: '"' + (m.group(2) + m.group(3)), joined)
        if joined.count("'") % 2 == 0 and joined.count('"') % 2 == 0:
            return joined, True
    # 处理像 /cart\n/update 这种 URL 被分行（即以 / 开头的行），把中间换行合并
    if re.search(r"/\s*\n\s*/", a + b):
        compact = re.sub(r"/\s*\n\s*/", "/", a + b)
        return compact, True
    return a + b, False


def smart_stitch(part_a: str, part_b: str, language: str = 'python') -> Tuple[str, dict]:
    """
    智能拼接两段生成内容：尝试最长重叠、修复被断开的字符串/URL、简单拼接，并对 Python 做 ast 校验。
    返回 (stitched_text, info_dict)
    info_dict 包含: {'method': 'overlap'|'concat'|'repair_string'|..., 'overlap_len': int, 'validated': bool, 'error': str|None}
    """
    info = {'method': None, 'overlap_len': 0, 'validated': False, 'error': None}

    # 1) 尝试最长重叠合并
    k = longest_overlap(part_a, part_b, min_len=4)
    if k > 0:
        stitched = part_a + part_b[k:]
        info.update({'method': 'overlap', 'overlap_len': k})
    else:
        # 2) 尝试修复断开字符串/URL的 heuristic
        stitched, did_fix = repair_broken_string_join(part_a, part_b)
        if did_fix:
            info.update({'method': 'repair_string_or_url', 'overlap_len': 0})
        else:
            # 3) 直接简单拼接
            stitched = part_a + part_b
            info.update({'method': 'simple_concat', 'overlap_len': 0})

    # 4) 语法校验（仅对 python）
    if language.lower() == 'python':
        ok, err = validate_python(stitched)
        info['validated'] = ok
        info['error'] = err
        if not ok:
            # 如果不通过，尝试更保守：取 part_a 的最后完整行结尾 + part_b
            lines = part_a.splitlines(keepends=True)
            for i in range(len(lines) - 1, -1, -1):
                candidate = ''.join(lines[:i + 1]) + part_b
                ok2, err2 = validate_python(candidate)
                if ok2:
                    info.update({'method': 'fallback_truncate_a_to_line_' + str(i), 'validated': True, 'error': None})
                    return candidate, info
            # 仍然失败，返回原 stitched 并保留错误
    return stitched, info


# ----------------- LLM / DeepSeek 交互模块 -----------------

def extract_initial_instruction(prompt: str) -> Tuple[str, str, str]:
    """
    只从用户提示词中解析修改指令。文件路径是硬编码的。
    """
    print("[解析] 正在从提示词中解析初始修改指令。")

    source_file = HARDCODED_SOURCE_FILE
    dest_file = HARDCODED_DEST_FILE

    # 简单地将整个用户输入作为初始修改指令
    initial_modification_instruction = prompt.strip()

    print(f"[解析] 源文件 (硬编码): {source_file}")
    print(f"[解析] 目标文件 (硬编码): {dest_file}")
    print(f"[解析] 初始修改指令: {initial_modification_instruction[:80]}...")

    return source_file, dest_file, initial_modification_instruction


def read_source_code(source_file: str) -> str:
    """实际从文件系统读取代码内容。"""
    if not os.path.exists(source_file):
        raise AutomationError(f"源文件未找到: {source_file}")
    print(f"[文件操作] 正在读取文件: {source_file}...")
    with open(source_file, 'r', encoding='utf-8') as f:
        return f.read()


def call_llm_for_continuation(
        step: int,
        context_code: str,  # For Step 1: source_code; For Step 2: continuation_part1
        instruction: str,  # 原始的修改指令
        full_source_code: Optional[str] = None  # 仅用于 Step 2 提供原始代码参考
) -> str:
    """
    通用 LLM 调用函数，根据步骤构造不同的提示。
    """
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "YOUR_DEEPSEEK_API_KEY":
        raise AutomationError("请在脚本开头配置您的 DEEPSEEK_API_KEY。")

    # --- 构造系统提示和用户消息 ---
    if step == 1:
        # 第一次调用：执行修改并开始生成新文件
        system_instruction = (
            "你是一个专业的代码修改助手。你将接收一个完整的源代码文件和一个修改需求。 "
            "你的任务是根据需求，在文件中执行修改，并生成**完整的、修改后的新文件**。 "
            "你的回复应该**只包含新生成的代码部分**，不要包含任何解释或Markdown格式。"
        )

        user_prompt = (
            f"请根据以下要求修改代码并开始生成完整的新文件，如果生成完整就在文件最底下写上`<!-- 文件结束，勿再生成 -->`，修改需求：{instruction}\n"
            f"完整源代码：\n```\n{context_code.strip()}\n```"
        )
    else:  # step == 2
        # 第二次调用：基于上一次的截断输出进行续写，并提供全部上下文
        system_instruction = (
            "你是一个专业的代码续写和结构补全助手。你将接收所有必要的上下文信息：原始代码、原始需求和上次生成的代码片段。 "
            "你的任务是根据这些信息，从上次生成的代码末尾处开始，继续续写文件剩余的所有内容，直到文件结构完整。 "
            "你的回复应该**只包含新生成的代码部分**，不要包含任何解释或Markdown格式。"
        )

        user_prompt = (
            f"如果第一次生成的截断代码已经满足需求，或者已经生成到 `<!-- 文件结束，勿再生成 -->`，请**直接停止生成**，不要继续生成任何代码。否则，按照下述提示，继续生成剩余的代码：\n```\n\n"
            f"以下是【原始源代码】（完整文件），仅用于参考文件结构：\n```ORIGINAL_SOURCE\n{full_source_code.strip()}\n```\n\n"
            f"以下是【第一次生成的被截断代码】。这是你上次工作的截止点：\n```PARTIAL_CODE\n{context_code.strip()}\n```\n\n"
            f"如果第一次生成的截断代码已经满足需求，或者已经生成到 `<!-- 文件结束，勿再生成 -->`，请**直接停止生成**，不要继续生成任何代码。否则，按照下述提示，继续生成剩余的代码：\n```\n\n"
            f"原始修改需求是：【{instruction}】\n\n"
            f"请根据此需求和原始源代码，从上一次生成的代码结尾处开始，继续生成剩余的 HTML/Jinja 代码，直到文件结构完整（包括 </body></html>）。**绝对不要重复已有的代码或任何解释**。"
        )

    # DeepSeek API 调用
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}'
    }

    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f"[LLM请求] 尝试调用 DeepSeek API (步骤 {step}, 第 {attempt + 1} 次)...")
            response = requests.post(
                API_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=API_TIMEOUT_SECONDS
            )
            response.raise_for_status()

            result = response.json()
            text = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

            if not text:
                error_msg = result.get('error', {}).get('message', 'LLM返回内容为空或格式不正确。')
                raise AutomationError(error_msg)

            print(f"[LLM请求] 步骤 {step} 代码生成成功。")
            return text

        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise AutomationError(f"API 调用重试失败，已达到最大尝试次数。") from e
            delay = 2 **(attempt + 1)
            print(f"遇到瞬时错误，等待 {delay} 秒后重试...")
            time.sleep(delay)
            continue
    raise AutomationError("DeepSeek API 调用重试失败，已达到最大尝试次数。")


def write_full_code_to_file(dest_file: str, part1_code: str, part2_code: str):
    """
    将 LLM 第一次和第二次生成的代码合并，写入目标文件。
    使用智能拼接（smart_stitch）并校验 Python 语法。
    如果第二次生成的内容为空，则直接使用第一次生成的内容。
    """
    # 清理代码片段内可能存在的代码块标记
    p1 = remove_triple_quotes(part1_code)
    p2 = remove_triple_quotes(part2_code)

    if not p2.strip():
        stitched = p1.strip()
        info = {'method': 'only_part1', 'validated': False, 'error': None}
        ok, err = validate_python(stitched)
        info['validated'] = ok
        info['error'] = err
    else:
        stitched, info = smart_stitch(p1, p2, language='python')

    # 进一步格式修复
    stitched = fix_code_indentation(stitched)

    # 如果最终语法不通过，仍然写出文件但记录警告信息到 stdout
    validated = info.get('validated', False)
    if not validated:
        print('\n[警告] 合并后的代码语法检测未通过：', info.get('error'))
        print('[建议] 请人工审查生成结果或尝试增加第二次生成的上下文并重试。\n')

    try:
        os.makedirs(os.path.dirname(dest_file) or '.', exist_ok=True)
        with open(dest_file, 'w', encoding='utf-8') as f:
            f.write(stitched)

        print(f"\n✅ 成功将完整代码写入目标文件: {dest_file}")
        print(f"完整代码长度: {len(stitched)} 字符")
        print(f"拼接信息: {json.dumps(info, ensure_ascii=False)}")

    except Exception as e:
        raise AutomationError(f"写入文件失败: {e}") from e


def run_code_continuation(user_prompt: str):
    """
    执行两次 LLM 调用和文件生成流程。
    """
    print("=" * 60)
    print("✨ DeepSeek 自动化代码修改/续写工具启动...")
    print("=" * 60)

    try:
        # 1. 解析初始提示词。
        source_file, dest_file, modification_instruction = extract_initial_instruction(user_prompt)

        # 2. 真实文件读取 (用于两次调用作为上下文)
        source_code = read_source_code(source_file)

        # 3. 第一次 LLM API 调用 (执行修改并生成前半部分)
        print("\n--- 步骤 1/2: 执行修改并生成文件前半部分 ---")
        continuation_part1 = call_llm_for_continuation(
            step=1,
            context_code=source_code,
            instruction=modification_instruction
        )
        print(f"  > Part 1 (前 500 字符): {continuation_part1[:500]}...")

        # 检查第一次生成的内容是否已经完整
        if "<!-- 文件结束，勿再生成 -->" in continuation_part1:
            print("\n--- 第一次调用已经生成完整代码，跳过第二次调用 ---")
            continuation_part2 = ""
        else:
            # 4. 第二次 LLM API 调用 (基于第一次的输出进行续写，并提供完整上下文)
            print("\n--- 步骤 2/2: 基于第一次结果进行续写 (携带所有上下文) ---")
            continuation_part2 = call_llm_for_continuation(
                step=2,
                context_code=continuation_part1,  # 第一次生成的代码作为起始点
                instruction=modification_instruction,  # 原始修改指令
                full_source_code=source_code  # 完整的原始代码
            )
            print(f"  > Part 2 (前 500 字符): {continuation_part2[:500]}...")

        # 5. 合并并写入新文件
        write_full_code_to_file(dest_file, continuation_part1, continuation_part2)

        print("\n" + "=" * 60)
        print("🚀 自动化流程成功完成。请检查生成的 123.py 文件。")
        print("【注意】此方法高度依赖 LLM 准确续写，但提供了最大的上下文支持。")
        print("=" * 60)

    except AutomationError as e:
        print(f"\n❌ 流程失败: {e}")
        print("\n请检查文件是否存在、API Key 和模型名称配置。")
    except Exception as e:
        print(f"\n致命错误: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("请输入修改代码的提示词:")
    print("【示例】请在侧边栏的“账户充值”链接之后添加一个新的导航项“订单管理”链接。")
    print("【注意】文件路径仍然硬编码:")
    print(f"  源文件: {HARDCODED_SOURCE_FILE}")
    print(f"  目标文件: {HARDCODED_DEST_FILE}")
    print("=" * 50)

    user_input_prompt = input(">>> ")

    # 运行主流程
    run_code_continuation(user_input_prompt)
