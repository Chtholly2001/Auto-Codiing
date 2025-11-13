# B站视频预览与跳转平台

一个简洁美观的B站视频预览平台，用户可以看到视频信息，点击后跳转到B站原视频页面。

## 项目结构

```
bilibili-preview-platform/
├── README.md              # 项目说明文档
├── app.py                 # Flask后端应用
├── requirements.txt       # Python依赖包列表
├── static/               # 静态资源目录
│   ├── css/
│   │   └── style.css     # 样式文件
│   └── js/
│       └── main.js       # JavaScript文件
└── templates/            # 模板文件目录
    ├── base.html         # 基础模板
    └── index.html        # 主页面模板
```

## 功能说明

1. **视频预览卡片**：展示视频封面、标题、播放量、弹幕数、发布时间、UP主信息和视频描述
2. **交互效果**：
   - 卡片悬停时有上浮和阴影加深效果
   - 点击"前往B站观看完整视频"按钮会跳转到指定B站视频页面
3. **响应式设计**：在手机等小屏幕设备上会自动调整布局
4. **动态数据**：支持通过后端API获取视频信息

## 运行方法

### 环境要求
- Python 3.7+
- Flask 2.0+

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动应用
```bash
python app.py
```

### 访问应用
打开浏览器访问：http://localhost:5000

## 技术栈

- 后端：Flask
- 前端：HTML5, CSS3, JavaScript
- 样式：响应式设计，CSS Grid/Flexbox
