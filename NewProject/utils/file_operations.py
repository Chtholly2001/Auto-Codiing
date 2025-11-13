# project_generator/utils/file_operations.py
import os
import json
import re
from datetime import datetime
from typing import Dict, List, Any

# 尝试导入配置中的正则，如果失败则使用本地健壮性定义
try:
    # 假设原文件中有这个相对导入
    from project_generator.config import FILE_BLOCK_RE
except ImportError:
    # 健壮的正则表达式：允许匹配 \n---END_FILE--- 或直接匹配字符串末尾($)
    # 这是修复无限循环的关键
    FILE_BLOCK_RE = re.compile(r"---FILE:\s*(?P<path>[^\n]+)\n(?P<content>.*?)(?:\n---END_FILE---|$)", re.DOTALL)


def parse_files_from_model(text: str) -> Dict[str, str]:
    """从模型输出的文本中解析出文件块。"""
    files: Dict[str, str] = {}
    for m in FILE_BLOCK_RE.finditer(text):
        path = m.group('path').strip()
        content = m.group('content')
        files[path] = content
    return files


def parse_files_from_model_with_continuation(text: str) -> Dict[str, Dict[str, Any]]:
    """
    从模型输出解析文件，同时检测是否被截断。
    此方法依赖于模型在截断处添加 "---TRUNCATED---" 标记。
    """
    files: Dict[str, Dict[str, Any]] = {}
    matches = list(FILE_BLOCK_RE.finditer(text))

    for m in matches:
        path = m.group('path').strip()
        content = m.group('content')

        # 显式截断标记检查
        is_truncated = "---TRUNCATED---" in content

        files[path] = {
            # 移除标记并清理末尾空白
            "content": content.replace("---TRUNCATED---", "").rstrip(),
            "truncated": is_truncated
        }

    return files


def sanitize_path(p: str) -> str:
    """清理文件路径，防止路径遍历或绝对路径。"""
    p = os.path.normpath(p)
    if os.path.isabs(p) or p.startswith('..'):
        # 抛出异常或返回清理后的路径
        raise ValueError(f"禁止使用绝对路径或父目录路径: {p}")
    return p


def write_files(files: Dict[str, str], base_dir: str):
    """将文件内容写入磁盘，并为脚本文件设置执行权限。"""
    for path, content in files.items():
        try:
            path = sanitize_path(path)
        except ValueError as e:
            print(f"⚠️  跳过写入文件: {path} - {e}")
            continue

        full = os.path.join(base_dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)

        # 备份已有文件
        if os.path.exists(full):
            try:
                ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                bak = full + f".bak.{ts}"
                with open(full, 'rb') as fr, open(bak, 'wb') as fw:
                    fw.write(fr.read())
                print(f"备份：{full} -> {bak}")
            except Exception:
                pass

        with open(full, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"写入：{full}")

        # 尝试设置执行权限
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

    # 过滤列表，只保留常见的文本/代码文件
    allowed_extensions = (
        '.py', '.md', '.txt', '.cfg', '.ini', '.json', '.yml', '.yaml',
        '.html', '.jinja', '.j2', '.css', '.js', '.ts', '.jsx', '.tsx',
        '.vue', '.sh', '.go', '.java', '.c', '.cpp', '.h', '.hpp', '.gitignore',
        '.dockerfile', '.properties', '.xml', '.toml', '.lock'
    )

    for root, _, files in os.walk(base_dir):
        for fn in files:
            # 过滤只保留文本/代码文件，并排除备份文件
            if any(fn.endswith(ext) for ext in allowed_extensions) and '.bak.' not in fn:
                full_path = os.path.join(root, fn)
                relative_path = os.path.relpath(full_path, base_dir)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data[relative_path] = f.read()
                except Exception as e:
                    print(f"警告：无法读取文件 {relative_path}: {e}")
    return data