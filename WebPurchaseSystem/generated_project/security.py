import bcrypt
import hashlib
import secrets
import re
from functools import wraps
from flask import session, redirect, url_for, flash, request, abort

def hash_password(password):
    """使用bcrypt安全哈希密码"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, hashed):
    """验证密码"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_csrf_token():
    """生成CSRF令牌"""
    return secrets.token_urlsafe(32)

def validate_input(text, max_length=1000):
    """验证和清理用户输入"""
    if not text:
        return ""

    # 限制长度
    text = str(text)[:max_length]

    # 移除潜在的XSS字符
    dangerous_chars = ['<', '>', '"', "'", '&', 'javascript:', 'onload=', 'onerror=']
    for char in dangerous_chars:
        text = text.replace(char, '')

    return text.strip()

def sanitize_html(text):
    """清理HTML内容"""
    if not text:
        return ""

    # 简单的HTML标签清理
    import html
    return html.escape(text)

def require_login(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录！', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录！', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('需要管理员权限！', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def require_user(f):
    """普通用户权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录！', 'error')
            return redirect(url_for('login'))
        if session.get('role') == 'admin':
            flash('管理员不能执行此操作！', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def validate_csrf_token():
    """验证CSRF令牌"""
    if request.method == "POST":
        token = request.form.get('csrf_token')
        if not token or token != session.get('csrf_token'):
            abort(403)

def rate_limit(max_requests=10, window=60):
    """简单的速率限制装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 这里可以实现更复杂的速率限制逻辑
            # 目前只是简单的示例
            return f(*args, **kwargs)
        return decorated_function
    return decorator
