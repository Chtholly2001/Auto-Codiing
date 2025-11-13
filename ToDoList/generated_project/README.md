# ToDoList应用

一个轻量级、前后端分离的待办事项管理Web应用，允许用户高效地创建、查看、更新和删除任务。

## 项目结构

```
todolist-app/
├── backend/
│   ├── app.py
│   ├── models.py
│   ├── database.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── README.md
```

## 功能说明

### 前端功能
- 任务列表展示：清晰展示所有待办事项，区分"未完成"和"已完成"状态
- 添加新任务：提供输入框和按钮，快速添加新的待办事项
- 标记完成/未完成：每个任务前有复选框，点击切换任务完成状态
- 删除任务：每个任务旁有删除按钮，点击删除对应任务
- 响应式界面：简洁美观的用户界面

### 后端功能
- RESTful API：提供标准的REST API供前端调用
- 任务管理接口：
  - `GET /api/tasks`：获取所有任务列表
  - `POST /api/tasks`：创建新任务
  - `PUT /api/tasks/<id>`：更新任务详细信息
  - `DELETE /api/tasks/<id>`：删除指定任务
- 数据持久化：使用SQLite数据库存储任务数据

## 技术栈

### 后端
- Python Flask
- SQLite数据库
- Flask-CORS（支持跨域请求）

### 前端
- 原生JavaScript
- HTML5
- CSS3

## 运行方法


### 方式二：分别启动前后端
```bash
# 启动后端
cd backend
pip install -r requirements.txt
python app.py

# 启动前端（在另一个终端）
# 用浏览器打开 frontend/index.html
```

访问应用：http://localhost:5000

## API接口说明

### 获取所有任务
- **URL**: `GET /api/tasks`
- **响应**: 任务列表JSON数组

### 创建任务
- **URL**: `POST /api/tasks`
- **Body**: `{"title": "任务内容"}`
- **响应**: 创建的任务对象

### 更新任务
- **URL**: `PUT /api/tasks/<id>`
- **Body**: `{"title": "新内容", "completed": true/false}`
- **响应**: 更新后的任务对象

### 删除任务
- **URL**: `DELETE /api/tasks/<id>`
- **响应**: 删除成功消息
