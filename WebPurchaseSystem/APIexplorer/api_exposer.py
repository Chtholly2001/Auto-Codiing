# file: api_exposer.py

import hashlib
import json
from typing import Dict, List, Any
from pathlib import Path
import ast


class ProfessionalCodeParser:
    """专业的代码解析器，使用AST进行精确分割"""

    def __init__(self):
        self.function_index = {}

    def parse_with_ast(self, source_code: str) -> Dict[str, Any]:
        """
        使用AST精确解析Python代码
        - symbolName: parse_with_ast
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
                'elements': all_elements
            }
        except SyntaxError as e:
            return {'error': f'语法错误: {str(e)}'}

    def _extract_functions_from_ast(self, tree: ast.AST, source: str) -> List[Dict]:
        """
        从AST中提取函数定义
        - symbolName: _extract_functions_from_ast
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
                    'args': [arg.arg for arg in node.args.args]
                })

        return functions

    def _extract_classes_from_ast(self, tree: ast.AST, source: str) -> List[Dict]:
        """
        从AST中提取类定义
        - symbolName: _extract_classes_from_ast
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
                    'type': 'class'
                })

        return classes

    def _extract_methods_from_ast(self, tree: ast.AST, source: str) -> List[Dict]:
        """
        从AST中提取方法定义
        - symbolName: _extract_methods_from_ast
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
                        'class': parent_class
                    })

        return methods

    # 在 symbolName: ProjectAPIExposer 类中扩展文件处理能力
    def _parse_file_by_type(self, content: str, file_path: str) -> Dict[str, Any]:
        """
        根据文件类型选择合适的解析器
        - symbolName: _parse_file_by_type
        """
        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension == '.py':
            return self._parse_python_file(content, file_path)
        elif file_extension in ['.html', '.jinja', '.j2']:
            return self._parse_html_template(content, file_path)
        elif file_extension == '.json':
            return self._parse_json_file(content, file_path)
        elif file_extension in ['.md', '.txt']:
            return self._parse_text_file(content, file_path)
        elif file_extension == '.css':
            return self._parse_css_file(content, file_path)
        else:
            # 默认处理为文本文件
            return self._parse_generic_file(content, file_path)

    def _generate_hash(self, name: str) -> str:
        """
        生成名称哈希
        - symbolName: _generate_hash
        """
        return hashlib.sha256(name.encode()).hexdigest()[:16]


class AdvancedAPIExposer:
    """高级API暴露器"""

    def __init__(self):
        self.parser = ProfessionalCodeParser()
        self.index_table = {}

    def expose_api(self, file_content: str, file_path: str = "") -> Dict[str, Any]:
        """
        暴露API接口
        - symbolName: expose_api
        """
        result = self.parser.parse_with_ast(file_content)

        if 'error' not in result:
            # 构建哈希索引表
            all_elements = result.get('elements', [])

            for element in all_elements:
                hash_key = self.parser._generate_hash(element['name'])
                self.index_table[hash_key] = {
                    'element': element,
                    'file_path': file_path
                }

        return result

    def query_element(self, element_name: str) -> Dict:
        """
        查询代码元素
        - symbolName: query_element
        """
        hash_key = self.parser._generate_hash(element_name)
        return self.index_table.get(hash_key, {})

    def get_all_elements(self) -> List[str]:
        """
        获取所有代码元素名称
        - symbolName: get_all_elements
        """
        return [info['element']['name'] for info in self.index_table.values()]


class MultiLanguageParser:
    """多语言代码解析器"""

    def __init__(self):
        self.exposer = AdvancedAPIExposer()

    def parse_code(self, code: str, language: str = "python") -> Dict:
        """
        解析指定语言的代码
        - symbolName: parse_code
        """
        if language.lower() == "python":
            return self.exposer.expose_api(code)
        else:
            # 其他语言可在此扩展
            return {
                "status": "unsupported",
                "message": f"当前版本暂不支持 {language} 语言"
            }
