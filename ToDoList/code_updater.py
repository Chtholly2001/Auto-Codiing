# project_generator/code_updater.py
import ast
import re
from typing import Dict, List


class CodeBlockUpdater:
    """代码块更新器，实现精准的代码块级别更新"""

    def update_code_blocks(self, original_content: str, updates: List[Dict]) -> str:
        """
        更新代码块
        updates格式: [{'name': 'function_name', 'new_content': '...', 'type': 'function'}]
        """
        lines = original_content.split('\n')

        # 按照行号排序更新，从后往前避免行号偏移
        sorted_updates = sorted(updates, key=lambda x: x.get('start_line', 0), reverse=True)

        for update in sorted_updates:
            start_line = update.get('start_line', 1) - 1
            end_line = update.get('end_line', start_line + 1)

            # 替换代码块
            new_lines = update['new_content'].split('\n')
            lines[start_line:end_line] = new_lines

        return '\n'.join(lines)

    def apply_block_changes(self, file_path: str, block_updates: List[Dict]) -> bool:
        """应用代码块更新到文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            updated_content = self.update_code_blocks(original_content, block_updates)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            return True
        except Exception as e:
            print(f"更新文件 {file_path} 失败: {e}")
            return False
