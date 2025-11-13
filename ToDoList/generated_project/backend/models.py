"""
数据模型定义
"""

class Task:
    """任务模型"""
    
    def __init__(self, id=None, title="", completed=False, priority="medium", due_date=None, tags=None, created_at=None):
        self.id = id
        self.title = title
        self.completed = completed
        self.priority = priority
        self.due_date = due_date
        self.tags = tags
        self.created_at = created_at
    
    def to_dict(self):
        """将任务对象转换为字典"""
        return {
            'id': self.id,
            'title': self.title,
            'completed': self.completed,
            'priority': self.priority,
            'due_date': self.due_date,
            'tags': self.tags,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建任务对象"""
        return cls(
            id=data.get('id'),
            title=data.get('title', ''),
            completed=data.get('completed', False),
            priority=data.get('priority', 'medium'),
            due_date=data.get('due_date'),
            tags=data.get('tags'),
            created_at=data.get('created_at')
        )
    
    @classmethod
    def from_row(cls, row):
        """从数据库行创建任务对象"""
        # 将 sqlite3.Row 转换为字典，或者使用安全的字段访问
        return cls(
            id=row['id'],
            title=row['title'],
            completed=bool(row['completed']),
            priority=row['priority'] if 'priority' in row.keys() else 'medium',
            due_date=row['due_date'] if 'due_date' in row.keys() else None,
            tags=row['tags'] if 'tags' in row.keys() else None,
            created_at=row['created_at']
        )
    
    def validate(self):
        """验证任务数据的有效性 - 增强版本"""
        if not isinstance(self.title, str):
            raise ValueError("标题必须是字符串")
        
        if len(self.title.strip()) == 0:
            raise ValueError("标题不能为空")
        
        if len(self.title) > 255:
            raise ValueError("标题长度不能超过255个字符")
        
        if not isinstance(self.completed, bool):
            raise ValueError("completed字段必须是布尔值")
        
        # 为可能缺失的字段提供默认值
        if not hasattr(self, 'priority') or self.priority is None:
            self.priority = 'medium'
        
        valid_priorities = ['low', 'medium', 'high']
        if self.priority not in valid_priorities:
            raise ValueError(f"优先级必须是 {', '.join(valid_priorities)}")
        
        if not hasattr(self, 'tags'):
            self.tags = None
        
        if self.tags and not isinstance(self.tags, str):
            raise ValueError("标签必须是字符串")
        
        return True