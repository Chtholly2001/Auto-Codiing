from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import os
import json
from datetime import datetime
import hashlib
from security import hash_password, verify_password, require_login, require_admin, require_user, generate_csrf_token
from database import DatabaseManager
from forms import BuyProductForm, RechargeForm, AddressForm, LoginForm, RegisterForm, ProductForm

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# 初始化数据库管理器
db = DatabaseManager()

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/')
def index():
    """首页"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    products = db.get_products()
    users = db.get_users()

    total_products = len(products)
    total_users = len(users)

    # 计算用户余额 - 管理员显示店铺余额，普通用户显示个人余额
    current_user = db.get_user_by_id(session['user_id'])
    if session.get('role') == 'admin':
        user_balance = db.get_shop_balance()  # 管理员显示店铺余额
    else:
        user_balance = current_user['balance'] if current_user else 0

    # 获取当前时间
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return render_template('index.html',
                           total_products=total_products,
                           total_users=total_users,
                           user_balance=user_balance,
                           username=session.get('username'),
                           role=session.get('role'),
                           current_time=current_time,
                           love_message="晚上好朋友")

@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    # 确保session中有CSRF令牌
    if 'csrf_token' not in session:
        session['csrf_token'] = generate_csrf_token()

    if request.method == 'POST':
        # 验证CSRF令牌
        if request.form.get('csrf_token') != session.get('csrf_token'):
            flash('无效的请求令牌！', 'error')
            return render_template('login.html')

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # 基本验证
        if not username or not password:
            flash('请填写完整的登录信息！', 'error')
            return render_template('login.html')

        user = db.get_user_by_username(username)
        if user and verify_password(password, user['password']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['csrf_token'] = generate_csrf_token()  # 生成新的CSRF令牌
            # 记录登录时间
            session['login_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            flash('登录成功！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误！', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    # 确保session中有CSRF令牌
    if 'csrf_token' not in session:
        session['csrf_token'] = generate_csrf_token()

    if request.method == 'POST':
        # 验证CSRF令牌
        if request.form.get('csrf_token') != session.get('csrf_token'):
            flash('无效的请求令牌！', 'error')
            return render_template('register.html')

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # 基本验证
        if not username or not password or not confirm_password:
            flash('请填写完整的注册信息！', 'error')
            return render_template('register.html')

        if len(username) < 3 or len(username) > 20:
            flash('用户名长度必须在3-20个字符之间！', 'error')
            return render_template('register.html')

        if not username.replace('_', '').isalnum():
            flash('用户名只能包含字母、数字和下划线！', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('密码长度不能少于6个字符！', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('两次输入的密码不一致！', 'error')
            return render_template('register.html')

        # 检查用户名是否已存在
        if db.get_user_by_username(username):
            flash('用户名已存在！', 'error')
            return render_template('register.html')

        # 创建新用户 - 使用正确的密码哈希
        hashed_password = hash_password(password)
        db.create_user(username, hashed_password, 'user')
        flash('注册成功！请登录。', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    flash('已成功登出！', 'success')
    return redirect(url_for('login'))

@app.route('/profile')
@require_login
def profile():
    """用户个人资料"""
    user = db.get_user_by_id(session['user_id'])
    if not user:
        flash('用户信息获取失败！', 'error')
        return redirect(url_for('index'))

    # 根据用户角色计算正确的余额显示
    if session.get('role') == 'admin':
        try:
            user_balance = db.get_shop_balance()  # 管理员显示店铺余额
        except Exception as e:
            app.logger.error(f"获取店铺余额失败: {str(e)}")
            user_balance = 0.0
            flash('获取店铺余额失败，已显示默认值', 'warning')
    else:
        user_balance = user.get('balance', 0.0)  # 普通用户显示个人余额

    return render_template('profile.html', user=user, user_balance=user_balance)

@app.route('/profile/edit', methods=['GET', 'POST'])
@require_login
def edit_profile():
    """编辑个人资料"""
    user = db.get_user_by_id(session['user_id'])

    if request.method == 'POST':
        # 更新用户信息
        user['address'] = {
            'province': request.form.get('province', ''),
            'city': request.form.get('city', ''),
            'district': request.form.get('district', ''),
            'detail': request.form.get('detail', ''),
            'phone': request.form.get('phone', '')
        }
        db.save_user(user)
        flash('个人资料更新成功！', 'success')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', user=user)

@app.route('/products')
@require_login
def products():
    """商品列表"""
    products_list = db.get_products()
    return render_template('products.html', products=products_list)

@app.route('/search')
@require_login
def search_products():
    """商品搜索"""
    query = request.args.get('q', '').strip()
    if query:
        products = db.search_products(query)
    else:
        products = db.get_products()
    return render_template('products.html', products=products, search_query=query)

@app.route('/products/category/<category_name>')
@require_login
def products_by_category(category_name):
    """按分类浏览商品"""
    products = db.get_products_by_category(category_name)
    return render_template('products.html', products=products, current_category=category_name)

@app.route('/products/add', methods=['GET', 'POST'])
@require_admin
def add_product():
    """添加商品"""
    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price'))
        stock = int(request.form.get('stock'))
        category = request.form.get('category')
        description = request.form.get('description', '')

        db.create_product(name, price, stock, category, description)
        flash('商品添加成功！', 'success')
        return redirect(url_for('products'))

    return render_template('add_product.html')

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@require_admin
def edit_product(product_id):
    """编辑商品"""
    product = db.get_product_by_id(product_id)
    if not product:
        flash('商品不存在！', 'error')
        return redirect(url_for('products'))

    if request.method == 'POST':
        # 更新商品信息
        product['name'] = request.form.get('name', product['name'])
        product['price'] = float(request.form.get('price', product['price']))
        product['stock'] = int(request.form.get('stock', product['stock']))
        product['category'] = request.form.get('category', product['category'])
        product['description'] = request.form.get('description', product.get('description', ''))

        db.save_product(product)
        flash('商品更新成功！', 'success')
        return redirect(url_for('products'))

    return render_template('edit_product.html', product=product)

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@require_admin
def delete_product(product_id):
    """删除商品"""
    db.delete_product(product_id)
    flash('商品删除成功！', 'success')
    return redirect(url_for('products'))

@app.route('/buy/<int:product_id>', methods=['GET', 'POST'])
@require_user
def buy_product(product_id):
    """购买商品 - 只有普通用户可以购买"""
    # 这里已经使用 @require_user 装饰器，确保只有普通用户可以访问
    product = db.get_product_by_id(product_id)
    user = db.get_user_by_id(session['user_id'])

    if not product:
        flash('商品不存在！', 'error')
        return redirect(url_for('products'))

    form = BuyProductForm()

    if request.method == 'POST':
        # 手动处理表单数据，不依赖 WTForms 验证
        try:
            quantity = int(request.form.get('quantity', 0))
        except (ValueError, TypeError):
            flash('购买数量无效！', 'error')
            return render_template('buy_product.html', product=product, form=form)

        if quantity <= 0:
            flash('购买数量必须大于0！', 'error')
            return render_template('buy_product.html', product=product, form=form)

        if product['stock'] < quantity:
            flash('商品库存不足！', 'error')
            return render_template('buy_product.html', product=product, form=form)

        total_price = product['price'] * quantity

        if user['balance'] < total_price:
            flash('余额不足！', 'error')
            return render_template('buy_product.html', product=product, form=form)

        # 更新商品库存
        product['stock'] -= quantity
        db.save_product(product)

        # 更新用户余额
        user['balance'] -= total_price
        db.save_user(user)

        # 创建订单 - 初始状态为"未发货"
        order = db.create_order(user['id'], product_id, quantity, total_price)

        flash(f'购买成功！已扣除 {total_price} 元', 'success')
        return redirect(url_for('products'))

    # GET 请求时渲染表单
    return render_template('buy_product.html', product=product, form=form)

@app.route('/recharge', methods=['GET', 'POST'])
@require_login
def recharge():
    """用户充值"""
    # 管理员不能充值
    if session.get('role') == 'admin':
        flash('管理员不能进行充值操作！', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        amount = float(request.form['amount'])

        if amount <= 0:
            flash('充值金额必须大于0！', 'error')
            return redirect(url_for('recharge'))

        user = db.get_user_by_id(session['user_id'])
        user['balance'] += amount
        db.save_user(user)

        flash(f'充值成功！当前余额：{user["balance"]} 元', 'success')
        return redirect(url_for('index'))

    return render_template('recharge.html')

@app.route('/admin/users')
@require_admin
def user_management():
    """用户管理"""
    users = db.get_users()
    return render_template('user_management.html', users=users)

@app.route('/admin/users/<int:user_id>/update-role', methods=['POST'])
@require_admin
def update_user_role(user_id):
    """更新用户角色"""
    role = request.form.get('role')
    if role in ['admin', 'user']:
        user = db.get_user_by_id(user_id)
        if user:
            user['role'] = role
            db.save_user(user)
            flash('用户角色更新成功！', 'success')
        else:
            flash('用户不存在！', 'error')
    else:
        flash('无效的角色！', 'error')
    return redirect(url_for('user_management'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@require_admin
def delete_user(user_id):
    """删除用户"""
    if user_id == session['user_id']:
        flash('不能删除当前登录的用户！', 'error')
    else:
        db.delete_user(user_id)
        flash('用户删除成功！', 'success')
    return redirect(url_for('user_management'))

@app.route('/orders')
@require_login
def orders():
    """订单列表 - 用户查看自己的订单"""
    if session.get('role') == 'admin':
        # 管理员查看所有订单 - 重定向到管理员订单页面
        return redirect(url_for('admin_orders'))
    else:
        # 普通用户只查看自己的订单
        user_orders = db.get_orders_by_user(session['user_id'])
    return render_template('orders.html', orders=user_orders)

@app.route('/order/<int:order_id>')
@require_login
def order_detail(order_id):
    """订单详情页面"""
    # 获取所有订单
    all_orders = db.get_orders()

    # 查找指定ID的订单
    order = None
    for o in all_orders:
        if o['id'] == order_id:
            order = o
            break

    # 检查订单是否存在
    if not order:
        flash('订单不存在！', 'error')
        return redirect(url_for('orders'))

    # 普通用户只能查看自己的订单
    if session.get('role') != 'admin' and order['user_id'] != session['user_id']:
        flash('您无权查看此订单！', 'error')
        return redirect(url_for('orders'))

    return render_template('order_detail.html', order=order)

@app.route('/order/<int:order_id>/review', methods=['GET', 'POST'])
@require_login
def add_review(order_id):
    """添加商品评价"""
    order = db.get_order_by_id(order_id)
    if not order or order['user_id'] != session['user_id']:
        flash('订单不存在或无权评价', 'error')
        return redirect(url_for('orders'))
    
    if request.method == 'POST':
        rating = int(request.form.get('rating', 5))
        comment = request.form.get('comment', '').strip()
        db.add_review(order_id, order['product_id'], session['user_id'], rating, comment)
        flash('评价成功！', 'success')
        return redirect(url_for('orders'))
    
    return render_template('add_review.html', order=order)

@app.route('/admin/orders')
@require_admin
def admin_orders():
    """管理员订单管理 - 查看所有用户订单"""
    all_orders = db.get_orders()
    return render_template('admin_orders.html', orders=all_orders)

@app.route('/admin/orders/<int:order_id>/ship', methods=['POST'])
@require_admin
def ship_order(order_id):
    """发货订单"""
    order = db.get_order_by_id(order_id)
    if not order:
        flash('订单不存在！', 'error')
        return redirect(url_for('admin_orders'))

    if order['status'] != '未发货':
        flash('只能对未发货的订单进行发货操作！', 'error')
        return redirect(url_for('admin_orders'))

    # 更新订单状态为"已发货"
    db.update_order_status(order_id, '已发货')
    flash('订单已发货！', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/orders/<int:order_id>/confirm', methods=['POST'])
@require_login
def confirm_order(order_id):
    """确认收货"""
    order = db.get_order_by_id(order_id)
    if not order:
        flash('订单不存在！', 'error')
        return redirect(url_for('orders'))

    # 检查订单是否属于当前用户
    if order['user_id'] != session['user_id']:
        flash('您无权操作此订单！', 'error')
        return redirect(url_for('orders'))

    if order['status'] != '已发货':
        flash('只能对已发货的订单进行确认收货操作！', 'error')
        return redirect(url_for('orders'))

    try:
        # 更新订单状态为"已收货"
        if not db.update_order_status(order_id, '已收货'):
            flash('订单状态更新失败！', 'error')
            return redirect(url_for('orders'))

        # 将款项增加到店铺余额
        new_balance = db.update_shop_balance(order['total_price'])
        if new_balance is None:
            flash('店铺余额更新失败！', 'error')
            # 回滚订单状态 - 添加错误处理
            try:
                db.update_order_status(order_id, '已发货')
                flash('已回滚订单状态', 'warning')
            except Exception as rollback_error:
                app.logger.error(f"回滚订单状态失败: {str(rollback_error)}")
                flash('系统错误：订单状态回滚失败，请联系管理员', 'error')
            return redirect(url_for('orders'))

        flash(f'订单确认收货成功！款项 {order["total_price"]} 元已转入店铺余额。当前店铺余额：{new_balance} 元', 'success')

    except Exception as e:
        flash(f'操作失败：{str(e)}', 'error')
        # 记录错误日志
        app.logger.error(f"确认收货失败: {str(e)}")

    return redirect(url_for('orders'))

@app.route('/cart')
@require_user
def view_cart():
    """查看购物车 - 只有普通用户可以访问"""
    user_cart = db.get_cart_by_user_id(session['user_id'])
    cart_items = []
    total_price = 0

    if user_cart:
        for item in user_cart.get('items', []):
            product = db.get_product_by_id(item['product_id'])
            if product:
                item_total = product['price'] * item['quantity']
                cart_items.append({
                    'product': product,
                    'quantity': item['quantity'],
                    'total_price': item_total
                })
                total_price += item_total

    return render_template('cart.html',
                         cart_items=cart_items,
                         total_price=total_price)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
@require_user
def add_to_cart(product_id):
    """添加商品到购物车 - 只有普通用户可以访问"""
    product = db.get_product_by_id(product_id)
    if not product:
        flash('商品不存在！', 'error')
        return redirect(url_for('products'))

    try:
        quantity = int(request.form.get('quantity', 1))
    except (ValueError, TypeError):
        quantity = 1

    if quantity <= 0:
        flash('数量必须大于0！', 'error')
        return redirect(url_for('products'))

    if product['stock'] < quantity:
        flash('商品库存不足！', 'error')
        return redirect(url_for('products'))

    # 添加到购物车
    db.create_or_update_cart(session['user_id'], product_id, quantity)
    return redirect(url_for('products'))

@app.route('/cart/update/<int:product_id>', methods=['POST'])
@require_user
def update_cart_item(product_id):
    """修改购物车商品数量 - 只有普通用户可以访问"""
    try:
        # CSRF令牌验证
        if request.is_json:
            data = request.get_json() or {}
            csrf_token = data.get('csrf_token')
        else:
            data = request.form
            csrf_token = data.get('csrf_token')
        
        if not csrf_token or csrf_token != session.get('csrf_token'):
            return jsonify({'success': False, 'error': '无效的请求令牌'})
        
        quantity = int(data.get('quantity', 1))
        
        if quantity <= 0:
            # 数量为0或负数时，删除商品
            success = db.remove_from_cart(session['user_id'], product_id)
            return jsonify({'success': success, 'action': 'remove'})
        
        # 验证商品和库存
        product = db.get_product_by_id(product_id)
        if not product:
            return jsonify({'success': False, 'error': '商品不存在'})
        
        if product['stock'] < quantity:
            return jsonify({'success': False, 'error': f'商品库存不足，当前库存：{product["stock"]}'})
        
        # 更新购物车 - 使用设置数量模式
        db.create_or_update_cart(session['user_id'], product_id, quantity, set_quantity=True)
        return jsonify({'success': True, 'action': 'update'})
        
    except ValueError:
        return jsonify({'success': False, 'error': '数量格式无效'})
    except Exception as e:
        app.logger.error(f"更新购物车失败: {str(e)}")
        return jsonify({'success': False, 'error': '服务器错误'})

@app.route('/cart/remove/<int:product_id>', methods=['POST'])
@require_user
def remove_from_cart(product_id):
    """删除购物车商品 - 只有普通用户可以访问"""
    try:
        # CSRF令牌验证
        if request.is_json:
            csrf_token = request.json.get('csrf_token')
        else:
            csrf_token = request.form.get('csrf_token')
        
        if not csrf_token or csrf_token != session.get('csrf_token'):
            return jsonify({'success': False, 'error': '无效的请求令牌'})
        
        success = db.remove_from_cart(session['user_id'], product_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '删除失败，商品可能不存在'})
    except Exception as e:
        app.logger.error(f"删除购物车商品失败: {str(e)}")
        return jsonify({'success': False, 'error': '服务器错误'})

@app.route('/cart/checkout', methods=['POST'])
@require_user
def checkout_cart():
    """购物车结算 - 只有普通用户可以访问"""
    try:
        # CSRF令牌验证
        csrf_token = request.form.get('csrf_token')
        if not csrf_token or csrf_token != session.get('csrf_token'):
            flash('无效的请求令牌！', 'error')
            return redirect(url_for('view_cart'))

        user_cart = db.get_cart_by_user_id(session['user_id'])
        if not user_cart or not user_cart.get('items'):
            flash('购物车为空！', 'error')
            return redirect(url_for('view_cart'))

        cart_items = []
        total_price = 0

        # 计算总价并检查库存
        for item in user_cart.get('items', []):
            product = db.get_product_by_id(item['product_id'])
            if not product:
                flash(f'商品 {item["product_id"]} 不存在！', 'error')
                return redirect(url_for('view_cart'))

            if product['stock'] < item['quantity']:
                flash(f'商品 {product["name"]} 库存不足！', 'error')
                return redirect(url_for('view_cart'))

            item_total = product['price'] * item['quantity']
            cart_items.append({
                'product': product,
                'quantity': item['quantity'],
                'total_price': item_total
            })
            total_price += item_total

        # 检查用户余额
        user = db.get_user_by_id(session['user_id'])
        if user['balance'] < total_price:
            flash('余额不足！', 'error')
            return redirect(url_for('view_cart'))

        # 扣款
        user['balance'] -= total_price
        db.save_user(user)

        # 更新库存并创建订单（状态为"未发货"）
        for item in cart_items:
            product = item['product']
            product['stock'] -= item['quantity']
            db.save_product(product)

            # 创建订单 - 初始状态为"未发货"
            db.create_order(
                user['id'],
                product['id'],
                item['quantity'],
                item['total_price']
            )

        # 清空购物车
        db.clear_cart(session['user_id'])

        flash(f'结算成功！共支付 {total_price} 元，等待发货', 'success')
        return redirect(url_for('orders'))

    except Exception as e:
        flash(f'结算失败：{str(e)}', 'error')
        return redirect(url_for('view_cart'))

@app.route('/coupons')
@require_login
def coupons():
    """优惠券列表"""
    user_coupons = db.get_user_coupons(session['user_id'])
    return render_template('coupons.html', coupons=user_coupons)

@app.route('/coupon/apply', methods=['POST'])
@require_user
def apply_coupon():
    """应用优惠券"""
    coupon_code = request.form.get('coupon_code', '').strip()
    
    if not coupon_code:
        flash('请输入优惠券代码！', 'error')
        return redirect(url_for('view_cart'))
    
    # 验证优惠券
    coupon = db.get_coupon_by_code(coupon_code)
    if not coupon:
        flash('优惠券不存在或已失效！', 'error')
        return redirect(url_for('view_cart'))
    
    # 检查优惠券是否可用
    if not db.is_coupon_available(coupon_code, session['user_id']):
        flash('优惠券不可用或已达到使用限制！', 'error')
        return redirect(url_for('view_cart'))
    
    # 将优惠券应用到用户会话
    session['applied_coupon'] = coupon_code
    flash(f'优惠券 {coupon_code} 应用成功！', 'success')
    return redirect(url_for('view_cart'))

@app.route('/coupon/remove', methods=['POST'])
@require_user
def remove_coupon():
    """移除已应用的优惠券"""
    if 'applied_coupon' in session:
        session.pop('applied_coupon')
        flash('优惠券已移除！', 'success')
    return redirect(url_for('view_cart'))

# 错误处理
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)