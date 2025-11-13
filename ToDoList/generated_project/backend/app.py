import os
import sys
import json
import requests
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from database import init_db, get_db_connection_from_pool, check_database_health, upgrade_table_structure
import re
import traceback
from datetime import datetime
import pytz
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)
CORS(app)  # 启用跨域请求支持

# 初始化数据库
init_db()

def check_table_structure():
    """检查表结构是否完整"""
    try:
        with get_db_connection_from_pool() as conn:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [column[1] for column in cursor.fetchall()]
            expected_columns = ['id', 'title', 'completed', 'priority', 'due_date', 'tags', 'created_at']
            
            missing_columns = set(expected_columns) - set(columns)
            if missing_columns:
                return False, f"表结构不完整，缺失列: {missing_columns}"
            return True, "表结构完整"
    except Exception as e:
        return False, f"表结构检查失败: {str(e)}"

# 添加数据库健康检查
try:
    is_healthy, health_message = check_database_health()
    print(f"数据库健康检查: {health_message}")
    
    # 添加表结构检查
    structure_ok, structure_message = check_table_structure()
    print(f"表结构检查: {structure_message}")
    
    if not structure_ok:
        print("警告：表结构不完整，可能需要运行数据库迁移")
        
except Exception as e:
    print(f"数据库检查失败: {e}")

def error_response(message, status_code=400):
    """统一错误响应格式"""
    return jsonify({'error': message, 'code': status_code}), status_code

def validate_title(title):
    """验证任务标题"""
    if not title or not title.strip():
        return False, "任务标题不能为空"

    title = title.strip()
    if len(title) > 100:
        return False, "任务标题不能超过100个字符"

    # 移除HTML转义，只做恶意内容检测
    malicious_patterns = [
        r'<script.*?>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'vbscript:',
        r'expression\s*\('
    ]

    for pattern in malicious_patterns:
        if re.search(pattern, title, re.IGNORECASE):
            return False, "标题包含非法内容"

    return True, title

def generate_fallback_summary(tasks, total, completed, pending, rate, overdue):
    """生成降级总结"""
    current_time = datetime.now(pytz.timezone('Asia/Shanghai'))
    current_date_str = current_time.strftime('%Y年%m月%d日')
    
    summary_parts = []
    
    summary_parts.append(f"📊 任务分析总结 ({current_date_str})")
    summary_parts.append(f"✅ 完成情况: {completed}/{total} 个任务 ({rate:.1f}%)")
    
    if rate >= 80:
        summary_parts.append("🎉 做得很好！您的完成率很高，继续保持！")
    elif rate >= 50:
        summary_parts.append("💪 进度不错，再加把劲完成剩余任务！")
    else:
        summary_parts.append("🚀 刚开始起步，建议优先完成高优先级任务")
    
    if overdue:
        summary_parts.append(f"⚠️ 注意: 有 {len(overdue)} 个任务已逾期，请优先处理")
    
    if pending > 0:
        high_priority = [t for t in tasks if not t['completed'] and t.get('priority') == 'high']
        if high_priority:
            summary_parts.append(f"🎯 建议优先完成 {len(high_priority)} 个高优先级任务")
    
    summary_parts.append("💡 提示: 为任务设置明确的截止日期可以提高完成率")
    
    return '\n\n'.join(summary_parts)

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取所有任务"""
    try:
        with get_db_connection_from_pool() as conn:
            cursor = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC')
            tasks = []
            for row in cursor.fetchall():
                from models import Task
                task = Task.from_row(row).to_dict()
                tasks.append(task)
            return jsonify(tasks)
    except Exception as e:
        return error_response(f'获取任务列表失败: {str(e)}', 500)

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """创建新任务"""
    try:
        data = request.get_json()

        if not data or 'title' not in data:
            return error_response('任务标题不能为空', 400)

        is_valid, title_or_error = validate_title(data['title'])
        if not is_valid:
            return error_response(title_or_error, 400)

        title = title_or_error
        priority = data.get('priority', 'medium')
        due_date = data.get('due_date')
        tags = data.get('tags')

        with get_db_connection_from_pool() as conn:
            cursor = conn.execute(
                'INSERT INTO tasks (title, completed, priority, due_date, tags) VALUES (?, ?, ?, ?, ?)',
                (title, False, priority, due_date, tags)
            )
            conn.commit()

            # 获取新创建的任务
            new_task_id = cursor.lastrowid
            cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (new_task_id,))
            row = cursor.fetchone()
            from models import Task
            
            # 将 sqlite3.Row 转换为字典
            row_dict = dict(zip([col[0] for col in cursor.description], row))
            task = Task.from_row(row_dict)

            return jsonify(task.to_dict()), 201
    except Exception as e:
        return error_response(f'创建任务失败: {str(e)}', 500)

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """更新任务"""
    try:
        data = request.get_json()

        if not data:
            return error_response('没有提供更新数据', 400)

        with get_db_connection_from_pool() as conn:
            # 检查任务是否存在
            cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            if not row:
                return error_response('任务不存在', 404)

            # 构建更新语句 - 使用参数化查询避免SQL注入
            update_fields = []
            update_values = []

            if 'title' in data:
                is_valid, title_or_error = validate_title(data['title'])
                if not is_valid:
                    return error_response(title_or_error, 400)
                update_fields.append('title = ?')
                update_values.append(title_or_error)

            if 'completed' in data:
                update_fields.append('completed = ?')
                update_values.append(bool(data['completed']))

            if 'priority' in data:
                update_fields.append('priority = ?')
                update_values.append(data['priority'])

            if 'due_date' in data:
                update_fields.append('due_date = ?')
                update_values.append(data['due_date'])

            if 'tags' in data:
                update_fields.append('tags = ?')
                update_values.append(data['tags'])

            if not update_fields:
                return error_response('没有有效的更新字段', 400)

            update_values.append(task_id)

            # 使用参数化查询构建安全的更新语句
            placeholders = ', '.join(update_fields)
            update_query = f'UPDATE tasks SET {placeholders} WHERE id = ?'

            conn.execute(update_query, update_values)
            conn.commit()

            # 获取更新后的任务
            cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            from models import Task
            
            # 将 sqlite3.Row 转换为字典
            row_dict = dict(zip([col[0] for col in cursor.description], row))
            task = Task.from_row(row_dict)

            return jsonify(task.to_dict())
    except Exception as e:
        return error_response(f'更新任务失败: {str(e)}', 500)

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    try:
        with get_db_connection_from_pool() as conn:
            # 检查任务是否存在
            cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            if not cursor.fetchone():
                return error_response('任务不存在', 404)

            conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            conn.commit()

            return jsonify({'message': '任务删除成功'})
    except Exception as e:
        return error_response(f'删除任务失败: {str(e)}', 500)

@app.route('/api/tasks/export', methods=['GET'])
def export_tasks():
    """导出任务数据为JSON文件"""
    try:
        with get_db_connection_from_pool() as conn:
            cursor = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC')
            tasks = []
            for row in cursor.fetchall():
                from models import Task
                task = Task.from_row(row).to_dict()
                tasks.append(task)

            # 创建导出数据
            export_data = {
                'export_time': datetime.now(pytz.timezone('Asia/Shanghai')).isoformat(),
                'total_tasks': len(tasks),
                'completed_tasks': len([task for task in tasks if task['completed']]),
                'pending_tasks': len([task for task in tasks if not task['completed']]),
                'tasks': tasks
            }

            # 生成带时间戳的文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'todo_tasks_export_{timestamp}.json'

            # 返回JSON文件下载
            response = Response(
                json.dumps(export_data, ensure_ascii=False, indent=2),
                mimetype='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename={filename}',
                    'Content-Type': 'application/json; charset=utf-8'
                }
            )

            return response
    except Exception as e:
        return error_response(f'导出任务失败: {str(e)}', 500)

@app.route('/api/tasks/summary', methods=['POST'])
def generate_summary():
    """使用DeepSeek AI生成任务总结 - 增强版本"""
    try:
        # 获取任务数据
        with get_db_connection_from_pool() as conn:
            cursor = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC')
            tasks = []
            for row in cursor.fetchall():
                from models import Task
                task = Task.from_row(row).to_dict()
                tasks.append(task)

        if not tasks:
            return jsonify({'summary': '🎯 当前没有任务数据\n\n💡 建议：\n1. 开始添加您的第一个任务\n2. 为任务设置优先级和截止日期\n3. 完成后标记为完成，AI会为您分析进度'})

        # 构建更详细的任务统计
        total_tasks = len(tasks)
        completed_tasks = len([task for task in tasks if task['completed']])
        pending_tasks = total_tasks - completed_tasks
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # 按优先级统计
        high_priority = len([t for t in tasks if t.get('priority') == 'high'])
        medium_priority = len([t for t in tasks if t.get('priority') == 'medium'])
        low_priority = len([t for t in tasks if t.get('priority') == 'low'])
        
        # 检查逾期任务
        today = datetime.now().date()
        overdue_tasks = []
        for task in tasks:
            if task.get('due_date') and not task['completed']:
                try:
                    due_date = datetime.strptime(task['due_date'], '%Y-%m-%d').date()
                    if due_date < today:
                        overdue_tasks.append(task)
                except:
                    continue

        # 使用环境变量管理API密钥
        api_key = os.getenv('DEEPSEEK_API_KEY', 'sk-6572f61cfd644e039072109240b19529')
        if not api_key or api_key == 'your_deepseek_api_key_here':
            fallback_summary = generate_fallback_summary(tasks, total_tasks, completed_tasks, pending_tasks, completion_rate, overdue_tasks)
            return jsonify({
                'summary': fallback_summary,
                'statistics': {
                    'total_tasks': total_tasks,
                    'completed_tasks': completed_tasks,
                    'pending_tasks': pending_tasks,
                    'completion_rate': completion_rate,
                    'overdue_tasks': len(overdue_tasks)
                },
                'note': 'AI服务未配置，请联系管理员'
            })

        # 在构建提示词之前添加当前时间信息
        current_time = datetime.now(pytz.timezone('Asia/Shanghai'))
        current_date_str = current_time.strftime('%Y年%m月%d日')
        current_weekday = current_time.strftime('%A')  # 获取星期几

        # 优化提示词 - 注入时间信息
        prompt = f"""请基于当前时间 {current_date_str} ({current_weekday}) 分析以下待办事项数据并生成一个详细、实用的总结：

📊 任务统计概览：
- 总任务数：{total_tasks} 个
- 已完成：{completed_tasks} 个
- 待完成：{pending_tasks} 个
- 完成率：{completion_rate:.1f}%

🎯 优先级分布：
- 🔴 高优先级：{high_priority} 个
- 🟡 中优先级：{medium_priority} 个  
- 🟢 低优先级：{low_priority} 个

{'⚠️ 警告：有 ' + str(len(overdue_tasks)) + ' 个任务已逾期！' if overdue_tasks else '✅ 暂无逾期任务'}

📝 任务详情（前10个）：
{json.dumps([{
    '标题': task['title'][:50] + ('...' if len(task['title']) > 50 else ''),
    '状态': '✅ 已完成' if task['completed'] else '⏳ 进行中',
    '优先级': task.get('priority', 'medium'),
    '截止日期': task.get('due_date', '未设置')
} for task in tasks[:10]], ensure_ascii=False, indent=2)}

请用中文提供以下内容的分析总结：

🎯 整体进度评估：
- 基于当前时间 {current_date_str} 的完成情况分析
- 与理想进度的对比

📈 任务分布分析：
- 重点关注高优先级任务完成情况
- 基于当前时间点的任务难度和时间分配建议

⏰ 时间管理建议：
- 基于当前日期的截止日期管理提醒
- 任务排期优化建议

💡 行动建议：
- 基于当前时间点的下一步最应该完成的任务
- 应该如何合理安排时间完成任务
- 风险提示和注意事项

✨ 鼓励话语：
- 根据完成情况给予积极反馈

请保持回答实用、具体，控制在300字以内，使用emoji让内容更生动。"""

        # 调用DeepSeek API
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': 'deepseek-chat',
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.7,
            'max_tokens': 800
        }

        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            # 提供降级方案
            fallback_summary = generate_fallback_summary(tasks, total_tasks, completed_tasks, pending_tasks, completion_rate, overdue_tasks)
            return jsonify({
                'summary': fallback_summary,
                'statistics': {
                    'total_tasks': total_tasks,
                    'completed_tasks': completed_tasks,
                    'pending_tasks': pending_tasks,
                    'completion_rate': completion_rate,
                    'overdue_tasks': len(overdue_tasks)
                },
                'note': 'AI服务暂不可用，此为系统自动生成的分析'
            })

        result = response.json()
        summary = result['choices'][0]['message']['content'].strip()

        return jsonify({
            'summary': summary,
            'statistics': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'pending_tasks': pending_tasks,
                'completion_rate': completion_rate,
                'overdue_tasks': len(overdue_tasks)
            }
        })

    except requests.exceptions.Timeout:
        fallback_summary = generate_fallback_summary(tasks, total_tasks, completed_tasks, pending_tasks, completion_rate, overdue_tasks)
        return jsonify({
            'summary': fallback_summary,
            'statistics': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'pending_tasks': pending_tasks,
                'completion_rate': completion_rate,
                'overdue_tasks': len(overdue_tasks)
            },
            'note': 'AI分析超时，此为系统自动分析'
        })
    except requests.exceptions.RequestException as e:
        # 降级处理
        fallback_summary = generate_fallback_summary(tasks, total_tasks, completed_tasks, pending_tasks, completion_rate, overdue_tasks)
        return jsonify({
            'summary': fallback_summary,
            'statistics': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'pending_tasks': pending_tasks,
                'completion_rate': completion_rate,
                'overdue_tasks': len(overdue_tasks)
            },
            'note': 'AI服务暂时不可用，此为系统自动分析'
        })
    except Exception as e:
        return error_response(f'生成总结失败: {str(e)}', 500)

@app.route('/')
def serve_frontend():
    """提供前端主页面"""
    frontend_dir = os.path.join(os.path.dirname(__file__), '../frontend')
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """提供前端静态文件服务"""
    frontend_dir = os.path.join(os.path.dirname(__file__), '../frontend')
    return send_from_directory(frontend_dir, path)

@app.route('/api/')
def api_info():
    """API信息页面"""
    return jsonify({
        'message': 'ToDoList API 服务',
        'endpoints': {
            'tasks': '/api/tasks',
            'export': '/api/tasks/export',
            'summary': '/api/tasks/summary',
            'documentation': '请访问前端页面使用应用'
        }
    })

@app.teardown_appcontext
def close_database_connection(exception=None):
    """应用关闭时清理数据库连接池"""
    # SQLite 不使用连接池，无需特殊清理操作
    pass

if __name__ == '__main__':
    try:
        print("ToDoList后端服务启动中...")
        print("访问地址: http://localhost:5000")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"启动失败: {e}")
        traceback.print_exc()
    finally:
        # SQLite 不使用连接池，无需特殊清理操作
        pass