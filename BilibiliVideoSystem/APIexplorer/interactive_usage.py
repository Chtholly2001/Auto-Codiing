# project_generator/APIexplorer/interactive_usage.py
# file: interactive_usage.py

import os
import ast
import hashlib
import json
import re
from typing import Dict, List, Any
# 原来的代码（第10行）
# from .api_exposer import MultiLanguageParser, AdvancedAPIExposer

# 修改为
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from api_exposer import MultiLanguageParser, AdvancedAPIExposer

class ProjectAPIExposer:
    """项目级API暴露器，用于解析整个项目目录"""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.index_table = {}

    def parse_project(self) -> Dict[str, Any]:
        """
        解析整个项目目录
        - symbolName: parse_project
        """
        project_structure = {}

        # 遍历项目目录
        for root, _, files in os.walk(self.project_root):
            for file in files:
                # 支持多种文件类型
                if any(file.endswith(ext) for ext in ['.py', '.html', '.jinja', '.j2', '.json', '.css', '.md', '.txt']):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.project_root)

                    try:
                        # 尝试以UTF-8编码读取文件
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        # 如果UTF-8解码失败，尝试其他编码或跳过二进制文件
                        try:
                            with open(file_path, 'r', encoding='gbk') as f:
                                content = f.read()
                        except:
                            print(f"无法解码文件 {relative_path}，跳过该文件")
                            continue
                    except Exception as e:
                        print(f"解析文件 {relative_path} 时出错: {e}")
                        continue

                    try:
                        # 根据文件类型解析单个文件
                        file_elements = self._parse_file_by_type(content, relative_path)
                        project_structure[relative_path] = file_elements

                        # 建立索引
                        self._build_index(file_elements, relative_path)
                    except Exception as e:
                        print(f"解析文件 {relative_path} 时出错: {e}")

        return {
            'project_root': self.project_root,
            'files': project_structure,
            'total_elements': len(self.index_table)
        }

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

    def _parse_python_file(self, content: str, file_path: str) -> Dict[str, Any]:
        """
        解析Python文件
        - symbolName: _parse_python_file
        """
        try:
            tree = ast.parse(content)
            functions = self._extract_functions(tree, content)
            classes = self._extract_classes(tree, content)
            methods = self._extract_methods(tree, content)

            return {
                'functions': functions,
                'classes': classes,
                'methods': methods,
                'elements': functions + classes + methods,
                'type': 'python'
            }
        except SyntaxError as e:
            return {'error': f'语法错误: {str(e)}', 'type': 'python'}

    def _parse_html_template(self, content: str, file_path: str) -> Dict[str, Any]:
        """
        解析HTML模板文件
        - symbolName: _parse_html_template
        """
        elements = []

        # 提取模板中的表单
        form_matches = re.finditer(r'<form[^>]*>.*?</form>', content, re.DOTALL)
        for i, match in enumerate(form_matches, 1):
            elements.append({
                'name': f'form_{i}',
                'content': match.group(),
                'start_line': content[:match.start()].count('\n') + 1,
                'end_line': content[:match.end()].count('\n') + 1,
                'type': 'form'
            })

        # 提取模板中的url_for调用
        url_for_matches = re.finditer(r'url_for\([\'"]([^\'"]+)[\'"]', content)
        for match in url_for_matches:
            elements.append({
                'name': match.group(1),
                'content': match.group(),
                'start_line': content[:match.start()].count('\n') + 1,
                'end_line': content[:match.end()].count('\n') + 1,
                'type': 'url_for'
            })

        return {
            'elements': elements,
            'type': 'html'
        }

    def _parse_json_file(self, content: str, file_path: str) -> Dict[str, Any]:
        """
        解析JSON文件
        - symbolName: _parse_json_file
        """
        try:
            data = json.loads(content)
            elements = []

            # 如果是对象数组，为每个对象创建元素
            if isinstance(data, list):
                for i, item in enumerate(data):
                    elements.append({
                        'name': f'item_{i}',
                        'content': json.dumps(item, indent=2),
                        'start_line': 0,  # JSON文件难以确定具体行号
                        'end_line': 0,
                        'type': 'json_item'
                    })
            # 如果是对象，提取关键字段
            elif isinstance(data, dict):
                for key in data.keys():
                    elements.append({
                        'name': key,
                        'content': json.dumps(data[key], indent=2),
                        'start_line': 0,
                        'end_line': 0,
                        'type': 'json_field'
                    })

            return {
                'elements': elements,
                'type': 'json'
            }
        except json.JSONDecodeError as e:
            return {'error': f'JSON解析错误: {str(e)}', 'type': 'json'}

    def _parse_text_file(self, content: str, file_path: str) -> Dict[str, Any]:
        """
        解析文本文件（如README.md）
        - symbolName: _parse_text_file
        """
        lines = content.split('\n')
        elements = []

        # 提取标题
        for i, line in enumerate(lines):
            if line.startswith('#'):
                elements.append({
                    'name': line.strip('# ').replace(' ', '_'),
                    'content': line,
                    'start_line': i + 1,
                    'end_line': i + 1,
                    'type': 'header'
                })

        return {
            'elements': elements,
            'type': 'text'
        }

    def _parse_css_file(self, content: str, file_path: str) -> Dict[str, Any]:
        """
        解析CSS文件
        - symbolName: _parse_css_file
        """
        # 提取CSS选择器
        selector_matches = re.finditer(r'([^{]+)\s*{([^}]*)}', content)
        elements = []

        for i, match in enumerate(selector_matches, 1):
            selector = match.group(1).strip()
            rules = match.group(2).strip()

            elements.append({
                'name': selector.replace('.', '').replace('#', '').replace(' ', '_').replace(':', '_'),
                'content': match.group(),
                'start_line': content[:match.start()].count('\n') + 1,
                'end_line': content[:match.end()].count('\n') + 1,
                'type': 'css_rule'
            })

        return {
            'elements': elements,
            'type': 'css'
        }

    def _parse_generic_file(self, content: str, file_path: str) -> Dict[str, Any]:
        """
        解析通用文件
        - symbolName: _parse_generic_file
        """
        # 对于不支持的文件类型，简单地将其作为一个整体元素处理
        return {
            'elements': [{
                'name': os.path.basename(file_path),
                'content': content,
                'start_line': 1,
                'end_line': len(content.split('\n')),
                'type': 'file'
            }],
            'type': 'generic'
        }

    def _extract_functions(self, tree: ast.AST, source: str) -> List[Dict]:
        """
        提取函数定义
        - symbolName: _extract_functions
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

                # 如果在类内部，则跳过（由_extract_methods处理）
                if in_class:
                    continue

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

    def _extract_classes(self, tree: ast.AST, source: str) -> List[Dict]:
        """
        提取类定义
        - symbolName: _extract_classes
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

    def _extract_methods(self, tree: ast.AST, source: str) -> List[Dict]:
        """
        提取方法定义
        - symbolName: _extract_methods
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

    def _build_index(self, file_elements: Dict[str, Any], file_path: str):
        """
        为文件元素建立索引
        - symbolName: _build_index
        """
        elements = file_elements.get('elements', [])
        for element in elements:
            # 使用文件路径和元素名生成唯一标识
            identifier = f"{file_path}:{element['name']}"
            hash_key = self._generate_hash(identifier)

            self.index_table[hash_key] = {
                'element': element,
                'file_path': file_path,
                'full_identifier': identifier
            }

    def _generate_hash(self, identifier: str) -> str:
        """
        生成哈希值
        - symbolName: _generate_hash
        """
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]

    def query_element(self, element_name: str, file_path: str = None) -> List[Dict]:
        """
        查询代码元素
        - symbolName: query_element
        """
        results = []

        if file_path:
            # 精确查询特定文件中的元素
            identifier = f"{file_path}:{element_name}"
            hash_key = self._generate_hash(identifier)
            if hash_key in self.index_table:
                results.append(self.index_table[hash_key])
        else:
            # 模糊查询所有匹配的元素
            for hash_key, info in self.index_table.items():
                if info['element']['name'] == element_name:
                    results.append(info)

        return results

    def get_project_structure(self) -> Dict[str, List[str]]:
        """
        获取项目结构信息
        - symbolName: get_project_structure
        """
        structure = {}
        for info in self.index_table.values():
            file_path = info['file_path']
            element_name = info['element']['name']

            if file_path not in structure:
                structure[file_path] = []
            structure[file_path].append(element_name)

        return structure


def interactive_demo():
    """
    API暴露器交互式演示程序
    - symbolName: interactive_demo
    """

    # 1. 创建实例
    # 使用 symbolName: MultiLanguageParser 创建解析器实例
    parser = MultiLanguageParser()
    print("=== API暴露器交互式演示 ===")
    print("1. 已创建解析器实例")

    while True:
        print("\n请选择操作:")
        print("1. 解析Python代码")
        print("2. 查询代码元素")
        print("3. 获取所有代码元素")
        print("4. 解析项目目录")
        print("5. 查询项目元素")
        print("6. 查看项目结构")
        print("7. 退出")

        choice = input("请输入选项 (1-7): ").strip()

        if choice == "1":
            # 2. 解析Python代码
            # 使用 symbolName: parse_code 解析代码
            print("\n请输入要解析的Python代码 (输入'END'结束):")
            code_lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                code_lines.append(line)

            if code_lines:
                code = "\n".join(code_lines)
                result = parser.parse_code(code, "python")

                if 'error' in result:
                    print(f"解析错误: {result['error']}")
                else:
                    print("解析成功!")
                    print(f"发现 {len(result.get('functions', []))} 个函数")
                    print(f"发现 {len(result.get('classes', []))} 个类")
                    print(f"发现 {len(result.get('methods', []))} 个方法")
            else:
                print("未输入有效代码")

        elif choice == "2":
            # 3. 查询代码元素
            # 使用 symbolName: query_element 查询特定元素
            element_name = input("请输入要查询的元素名称: ").strip()
            if element_name:
                element_info = parser.exposer.query_element(element_name)
                if element_info:
                    element_data = element_info['element']
                    print(f"\n元素 '{element_name}' 信息:")
                    print(f"  类型: {element_data['type']}")
                    print(f"  位置: 第{element_data['start_line']}行到第{element_data['end_line']}行")
                    if 'args' in element_data:
                        print(f"  参数: {element_data['args']}")
                    if 'class' in element_data:
                        print(f"  所属类: {element_data['class']}")
                    print(f"  内容:\n{element_data['content']}")
                else:
                    print(f"未找到元素 '{element_name}'")
            else:
                print("请输入有效的元素名称")

        elif choice == "3":
            # 4. 获取所有元素
            # 使用 symbolName: get_all_elements 获取所有代码元素
            all_elements = parser.exposer.get_all_elements()
            if all_elements:
                print(f"\n找到 {len(all_elements)} 个代码元素:")
                for i, element in enumerate(all_elements, 1):
                    print(f"  {i}. {element}")
            else:
                print("暂无代码元素，请先解析代码")

        elif choice == "4":
            # 解析项目目录
            project_path = input("请输入项目路径 (默认为当前目录): ").strip()
            if not project_path:
                project_path = "."

            if os.path.exists(project_path):
                project_exposer = ProjectAPIExposer(project_path)
                print("正在解析项目...")
                result = project_exposer.parse_project()
                print(f"解析完成! 发现 {result['total_elements']} 个代码元素")
                # 保存项目解析器实例供后续使用
                globals()['project_exposer'] = project_exposer
            else:
                print(f"项目路径 {project_path} 不存在")

        elif choice == "5":
            # 查询项目元素
            if 'project_exposer' not in globals():
                print("请先解析项目目录")
                continue

            element_name = input("请输入要查询的元素名称: ").strip()
            if element_name:
                results = globals()['project_exposer'].query_element(element_name)
                if results:
                    print(f"\n找到 {len(results)} 个匹配的元素:")
                    for i, result in enumerate(results, 1):
                        element_data = result['element']
                        print(f"  {i}. 文件: {result['file_path']}")
                        print(f"     元素: {element_data['name']}")
                        print(f"     类型: {element_data['type']}")
                        print(f"     位置: 第{element_data['start_line']}行到第{element_data['end_line']}行")
                        if 'args' in element_data:
                            print(f"     参数: {element_data['args']}")
                        if 'class' in element_data:
                            print(f"     所属类: {element_data['class']}")
                        print(f"     内容:")
                        print(element_data['content'])
                        print()
                else:
                    print(f"未找到元素 '{element_name}'")
            else:
                print("请输入有效的元素名称")

        elif choice == "6":
            # 查看项目结构
            if 'project_exposer' not in globals():
                print("请先解析项目目录")
                continue

            structure = globals()['project_exposer'].get_project_structure()
            print("\n项目结构:")
            for file_path, elements in structure.items():
                print(f"  {file_path}: {len(elements)} 个元素")
                for element in elements:
                    print(f"    - {element}")

        elif choice == "7":
            print("退出程序")
            break

        else:
            print("无效选项，请重新选择")


if __name__ == "__main__":
    # symbolName: __main__
    interactive_demo()
