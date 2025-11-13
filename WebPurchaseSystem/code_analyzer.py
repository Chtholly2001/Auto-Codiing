# file: code_analyzer.py
import ast
import hashlib
from typing import Dict, List, Any
from pathlib import Path


class CodeAnalyzer:
    """专业的代码解析器，使用AST进行精确分割"""

    def __init__(self):
        self.function_index = {}

    def parse_with_ast(self, source_code: str, file_path: str = "") -> Dict[str, Any]:
        """
        使用AST精确解析Python代码
        """
        try:
            tree = ast.parse(source_code)
            functions = self._extract_functions_from_ast(tree, source_code)
            classes = self._extract_classes_from_ast(tree, source_code)
            methods = self._extract_methods_from_ast(tree, source_code)

            # 建立精确索引
            all_elements = functions + classes + methods
            for element in all_elements:
                func_hash = self._generate_hash(element['name'])
                self.function_index[func_hash] = element

            return {
                'functions': functions,
                'classes': classes,
                'methods': methods,
                'elements': all_elements,
                'file_path': file_path
            }
        except SyntaxError as e:
            return {'error': f'语法错误: {str(e)}'}

    def _extract_functions_from_ast(self, tree: ast.AST, source: str) -> List[Dict]:
        """
        从AST中提取函数定义
        """
        functions = []
        lines = source.split('\n')

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 检查是否在类内部
                in_class = False
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef):
                        if parent.lineno <= node.lineno <= getattr(parent, 'end_lineno', float('inf')):
                            in_class = True
                            break

                # 如果在类内部，则跳过（由_extract_methods_from_ast处理）
                if in_class:
                    continue

                # 获取函数源码
                start_line = node.lineno - 1
                end_line = getattr(node, 'end_lineno', start_line + 1)

                function_source = '\n'.join(lines[start_line:end_line])

                functions.append({
                    'name': node.name,
                    'content': function_source,
                    'start_line': start_line + 1,
                    'end_line': end_line,
                    'type': 'function',
                    'file_path': ''
                })

        return functions

    def _extract_classes_from_ast(self, tree: ast.AST, source: str) -> List[Dict]:
        """
        从AST中提取类定义
        """
        classes = []
        lines = source.split('\n')

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                start_line = node.lineno - 1
                end_line = getattr(node, 'end_lineno', start_line + 1)

                class_source = '\n'.join(lines[start_line:end_line])

                classes.append({
                    'name': node.name,
                    'content': class_source,
                    'start_line': start_line + 1,
                    'end_line': end_line,
                    'type': 'class',
                    'file_path': ''
                })

        return classes

    def _extract_methods_from_ast(self, tree: ast.AST, source: str) -> List[Dict]:
        """
        从AST中提取类方法
        """
        methods = []
        lines = source.split('\n')

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 检查是否在类内部
                parent_class = None
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef):
                        if parent.lineno <= node.lineno <= getattr(parent, 'end_lineno', float('inf')):
                            parent_class = parent.name
                            break

                if parent_class:
                    start_line = node.lineno - 1
                    end_line = getattr(node, 'end_lineno', start_line + 1)

                    method_source = '\n'.join(lines[start_line:end_line])

                    methods.append({
                        'name': f"{parent_class}.{node.name}",
                        'content': method_source,
                        'start_line': start_line + 1,
                        'end_line': end_line,
                        'type': 'method',
                        'class': parent_class,
                        'file_path': ''
                    })

        return methods

    def _generate_hash(self, name: str) -> str:
        """
        生成名称哈希
        """
        return hashlib.sha256(name.encode()).hexdigest()[:16]

    def find_relevant_elements(self, query: str) -> List[Dict]:
        """
        根据查询词查找相关代码元素
        """
        relevant_elements = []
        query_lower = query.lower()

        for element in self.function_index.values():
            # 检查函数名、类名或方法名是否包含查询词
            if query_lower in element['name'].lower():
                relevant_elements.append(element)
                continue

            # 检查代码内容是否包含查询词
            if query_lower in element['content'].lower():
                relevant_elements.append(element)

        return relevant_elements
