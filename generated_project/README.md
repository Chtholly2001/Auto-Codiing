```
# 商品管理系统

这是一个基于Python的商品管理系统，支持用户的注册登录和商品的增删改查操作。

## 功能特性

- 用户注册和登录
- 商品列表展示
- 添加新商品
- 编辑商品信息
- 删除商品
- 商品搜索
- 用户余额充值
- 商品购买和库存管理

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动应用

```bash
python app.py
```

或者使用启动脚本：

```bash
chmod +x run.sh
./run.sh
```

## 使用说明

1. 启动应用后，访问 http://localhost:5000
2. 首次使用需要注册账号并登录
3. 在商品管理页面可以进行商品的增删改查操作
4. 支持按商品名称搜索商品
5. 用户可以通过充值页面进行余额充值
6. 在商品页面可以直接购买商品，系统会自动扣款和减少库存

## 如何将项目打包到GitHub

1. **创建GitHub仓库**
   - 登录GitHub账号
   - 点击右上角"+"号，选择"New repository"
   - 输入仓库名称和描述
   - 选择公开或私有
   - 不要勾选"Initialize this repository with a README"（因为已有README.md）

2. **本地Git初始化**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

3. **连接到GitHub仓库**
   ```bash
   git remote add origin https://github.com/Chtholly2001/Yursor.git
   git branch -M main
   git push -u origin main
   
   ```

4. **创建.gitignore文件**（可选但推荐）
   在项目根目录创建`.gitignore`文件，内容如下：
   ```
   __pycache__/
   *.pyc
   .env
   venv/
   .vscode/
   .idea/
   *.db
   *.sqlite3
   ```

## 安全说明

- 用户密码使用SHA-256哈希存储
- 生产环境请修改app.py中的secret_key
- 会话管理使用Flask session
```

   git init
   