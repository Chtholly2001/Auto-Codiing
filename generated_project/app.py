from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import json
import os
import hashlib

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # 生产环境请使用强密钥

# 数据文件路径
DATA_FILE = 'products.json'
USERS_FILE = 'users.json'

def load_products():
    """加载商品数据"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            # 如果JSON文件损坏或为空，返回空列表
            return []
    return []

def save_products(products):
    """保存商品数据"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

def load_users():
    """加载用户数据"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return []
    return []

def save_users(users):
    """保存用户数据"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password):
    """密码哈希函数"""
    return hashlib.sha256(password.encode()).hexdigest()

def is_logged_in():
    """检查用户是否已登录"""
    return 'user_id' in session

def get_current_user():
    """获取当前登录用户信息"""
    if is_logged_in():
        users = load_users()
        return next((u for u in users if u['id'] == session['user_id']), None)
    return None

@app.route('/')
def index():
    if is_logged_in():
        return redirect(url_for('product_management'))
    else:
        return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    if is_logged_in():
        return redirect(url_for('product_management'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # 验证输入
        if not username or not password:
            return render_template('register.html', error='用户名和密码不能为空')
        
        if password != confirm_password:
            return render_template('register.html', error='两次输入的密码不一致')
        
        users = load_users()
        
        # 检查用户名是否已存在
        if any(user['username'] == username for user in users):
            return render_template('register.html', error='用户名已存在')
        
        # 创建新用户
        new_user = {
            'id': len(users) + 1,
            'username': username,
            'password': hash_password(password),
            'balance': 0.0  # 初始余额为0
        }
        
        users.append(new_user)
        save_users(users)
        
        # 自动登录
        session['user_id'] = new_user['id']
        session['username'] = new_user['username']
        
        return redirect(url_for('product_management'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if is_logged_in():
        return redirect(url_for('product_management'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        users = load_users()
        user = next((u for u in users if u['username'] == username and u['password'] == hash_password(password)), None)
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('product_management'))
        else:
            return render_template('login.html', error='用户名或密码错误')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/products')
def product_management():
    """商品管理页面"""
    if not is_logged_in():
        return redirect(url_for('login'))
        
    products = load_products()
    search_query = request.args.get('search', '')
    
    if search_query:
        filtered_products = [p for p in products if search_query.lower() in p['name'].lower()]
    else:
        filtered_products = products
    
    user = get_current_user()
    return render_template('products.html', products=filtered_products, search_query=search_query, user=user)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    """添加商品"""
    if not is_logged_in():
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        description = request.form['description']
        
        products = load_products()
        
        new_product = {
            'id': len(products) + 1,
            'name': name,
            'price': price,
            'stock': stock,
            'description': description
        }
        
        products.append(new_product)
        save_products(products)
        
        return redirect(url_for('product_management'))
    
    return render_template('add_product.html')

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    """编辑商品"""
    if not is_logged_in():
        return redirect(url_for('login'))
        
    products = load_products()
    product = next((p for p in products if p['id'] == product_id), None)
    
    if not product:
        return redirect(url_for('product_management'))
    
    if request.method == 'POST':
        product['name'] = request.form['name']
        product['price'] = float(request.form['price'])
        product['stock'] = int(request.form['stock'])
        product['description'] = request.form['description']
        
        save_products(products)
        return redirect(url_for('product_management'))
    
    return render_template('edit_product.html', product=product)

@app.route('/delete_product/<int:product_id>')
def delete_product(product_id):
    """删除商品"""
    if not is_logged_in():
        return redirect(url_for('login'))
        
    products = load_products()
    products = [p for p in products if p['id'] != product_id]
    save_products(products)
    
    return redirect(url_for('product_management'))

@app.route('/recharge', methods=['GET', 'POST'])
def recharge():
    """用户充值"""
    if not is_logged_in():
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        amount = float(request.form['amount'])
        
        if amount <= 0:
            return render_template('recharge.html', error='充值金额必须大于0')
        
        users = load_users()
        user = next((u for u in users if u['id'] == session['user_id']), None)
        
        if user:
            user['balance'] = user.get('balance', 0.0) + amount
            save_users(users)
            return redirect(url_for('product_management'))
        else:
            return render_template('recharge.html', error='用户不存在')
    
    return render_template('recharge.html')

@app.route('/buy_product/<int:product_id>', methods=['POST'])
def buy_product(product_id):
    """购买商品"""
    if not is_logged_in():
        return jsonify({'success': False, 'message': '请先登录'})
    
    quantity = int(request.form.get('quantity', 1))
    
    if quantity <= 0:
        return jsonify({'success': False, 'message': '购买数量必须大于0'})
    
    products = load_products()
    product = next((p for p in products if p['id'] == product_id), None)
    
    if not product:
        return jsonify({'success': False, 'message': '商品不存在'})
    
    if product['stock'] < quantity:
        return jsonify({'success': False, 'message': '库存不足'})
    
    total_price = product['price'] * quantity
    
    users = load_users()
    user = next((u for u in users if u['id'] == session['user_id']), None)
    
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'})
    
    user_balance = user.get('balance', 0.0)
    
    if user_balance < total_price:
        return jsonify({'success': False, 'message': '余额不足'})
    
    # 扣款和更新库存
    user['balance'] = user_balance - total_price
    product['stock'] -= quantity
    
    save_users(users)
    save_products(products)
    
    return jsonify({
        'success': True, 
        'message': f'购买成功！花费 {total_price:.2f} 元，购买 {quantity} 件 {product["name"]}',
        'new_balance': user['balance']
    })

if __name__ == '__main__':
    app.run(debug=True)