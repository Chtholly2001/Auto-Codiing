import sqlite3
import os
from contextlib import contextmanager
import pytz
from datetime import datetime

# 使用绝对路径避免在不同目录下运行时找不到数据库文件
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'todolist.db')

def upgrade_table_structure(conn):
    """升级表结构，添加缺失的列"""
    try:
        cursor = conn.execute("PRAGMA table_info(tasks)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        # 定义需要添加的列
        columns_to_add = [
            ('priority', 'TEXT DEFAULT "medium"'),
            ('due_date', 'TEXT'),
            ('tags', 'TEXT')
        ]
        
        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                print(f"添加缺失的列: {column_name}")
                conn.execute(f'ALTER TABLE tasks ADD COLUMN {column_name} {column_type}')
        
        conn.commit()
        print("表结构升级完成")
        
    except Exception as e:
        print(f"表结构升级失败: {e}")
        raise

def init_db():
    """初始化数据库和表结构 - 增强版本"""
    try:
        # 确保数据库目录存在
        db_dir = os.path.dirname(DATABASE_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        with get_db_connection() as conn:
            # 检查表是否存在
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='tasks'
            """)
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                print("创建任务表...")
                conn.execute('''
                    CREATE TABLE tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        completed BOOLEAN NOT NULL DEFAULT FALSE,
                        priority TEXT DEFAULT 'medium',
                        due_date TEXT,
                        tags TEXT,
                        created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                    )
                ''')
                conn.commit()
                print("任务表创建成功")
            else:
                print("任务表已存在，检查表结构...")
                # 检查并添加缺失的列
                upgrade_table_structure(conn)
                
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        raise

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

def get_beijing_time():
    """获取北京时间"""
    beijing_tz = pytz.timezone('Asia/Shanghai')
    return datetime.now(beijing_tz)

@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器 - 增强版本"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        
        # 启用外键支持和WAL模式以提高性能
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        
        yield conn
        conn.commit()  # 确保事务提交
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

# 为了保持向后兼容性，保留这个函数名但内部使用简单连接
@contextmanager
def get_db_connection_from_pool():
    """SQLite 连接获取（简化版本，不使用连接池）"""
    with get_db_connection() as conn:
        yield conn

def close_db_pool():
    """关闭数据库连接池（SQLite 简化版本，实际无操作）"""
    # SQLite 不使用连接池，此函数为空实现以保持接口兼容性
    pass

def check_database_health():
    """检查数据库健康状态"""
    try:
        with get_db_connection() as conn:
            # 检查表是否存在
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='tasks'
            """)
            if not cursor.fetchone():
                return False, "任务表不存在"
                
            # 检查是否可以读写
            test_title = "数据库健康检查"
            cursor = conn.execute(
                "INSERT INTO tasks (title) VALUES (?)",
                (test_title,)
            )
            test_id = cursor.lastrowid
            
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (test_id,)
            )
            task = cursor.fetchone()
            
            conn.execute("DELETE FROM tasks WHERE id = ?", (test_id,))
            conn.commit()
            
            if task and task['title'] == test_title:
                return True, "数据库健康"
            else:
                return False, "数据库读写测试失败"
                
    except Exception as e:
        return False, f"数据库健康检查失败: {str(e)}"
