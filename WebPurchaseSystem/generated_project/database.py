import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

class DatabaseManager:
    """数据库管理器 - 统一管理所有数据操作"""
    
    def __init__(self, data_dir='.'):
        self.data_dir = data_dir
        self.lock = threading.Lock()
        
        # 数据文件路径
        self.users_file = os.path.join(data_dir, 'users.json')
        self.products_file = os.path.join(data_dir, 'products.json')
        self.orders_file = os.path.join(data_dir, 'orders.json')
        self.shop_balance_file = os.path.join(data_dir, 'shop_balance.json')
        self.carts_file = os.path.join(data_dir, 'carts.json')
        self.reviews_file = os.path.join(data_dir, 'reviews.json')
        
        # 初始化数据文件
        self._init_data_files()
    
    def _init_data_files(self):
        """初始化数据文件"""
        files = [self.users_file, self.products_file, self.orders_file, self.carts_file, self.reviews_file]
        for file_path in files:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
        
        # 初始化店铺余额文件
        if not os.path.exists(self.shop_balance_file):
            with open(self.shop_balance_file, 'w', encoding='utf-8') as f:
                json.dump({"balance": 0.0}, f, ensure_ascii=False, indent=2)
    
    def _read_json(self, file_path: str) -> List[Dict]:
        """读取JSON文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _write_json(self, file_path: str, data: List[Dict]):
        """写入JSON文件"""
        with self.lock:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 用户管理
    def get_users(self) -> List[Dict]:
        """获取所有用户"""
        return self._read_json(self.users_file)
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据ID获取用户"""
        users = self.get_users()
        return next((u for u in users if u['id'] == user_id), None)
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名获取用户"""
        users = self.get_users()
        return next((u for u in users if u['username'] == username), None)
    
    def save_user(self, user: Dict):
        """保存用户"""
        users = self.get_users()
        existing_index = next((i for i, u in enumerate(users) if u['id'] == user['id']), None)
        
        if existing_index is not None:
            users[existing_index] = user
        else:
            users.append(user)
        
        self._write_json(self.users_file, users)
    
    def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        users = self.get_users()
        users = [u for u in users if u['id'] != user_id]
        self._write_json(self.users_file, users)
        return True
    
    def create_user(self, username: str, password_hash: str, role: str = 'user') -> Dict:
        """创建新用户"""
        users = self.get_users()
        new_id = max([u['id'] for u in users], default=0) + 1
        
        user = {
            'id': new_id,
            'username': username,
            'password': password_hash,
            'role': role,
            'balance': 0.0,
            'created_at': datetime.now().isoformat(),
            'address': {
                'province': '',
                'city': '',
                'district': '',
                'detail': '',
                'phone': ''
            }
        }
        
        self.save_user(user)
        return user
    
    # 商品管理
    def get_products(self) -> List[Dict]:
        """获取所有商品"""
        return self._read_json(self.products_file)
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        """根据ID获取商品"""
        products = self.get_products()
        return next((p for p in products if p['id'] == product_id), None)
    
    def save_product(self, product: Dict):
        """保存商品"""
        products = self.get_products()
        existing_index = next((i for i, p in enumerate(products) if p['id'] == product['id']), None)
        
        if existing_index is not None:
            products[existing_index] = product
        else:
            products.append(product)
        
        self._write_json(self.products_file, products)

    def delete_product(self, product_id: int) -> bool:
        """删除商品"""
        products = self.get_products()
        products = [p for p in products if p['id'] != product_id]
        self._write_json(self.products_file, products)
        return True

    def create_product(self, name: str, price: float, stock: int, category: str, description: str = '') -> Dict:
        """创建新商品"""
        products = self.get_products()
        new_id = max([p['id'] for p in products], default=0) + 1

        product = {
            'id': new_id,
            'name': name,
            'price': price,
            'stock': stock,
            'category': category,
            'description': description,
            'created_at': datetime.now().isoformat()
        }

        self.save_product(product)
        return product

    def search_products(self, query: str) -> List[Dict]:
        """搜索商品"""
        products = self.get_products()
        query_lower = query.lower()
        return [p for p in products if query_lower in p['name'].lower() or 
                query_lower in p.get('description', '').lower()]

    def get_products_by_category(self, category: str) -> List[Dict]:
        """按分类获取商品"""
        products = self.get_products()
        return [p for p in products if p['category'] == category]

    # 订单管理
    def get_orders(self) -> List[Dict]:
        """获取所有订单"""
        return self._read_json(self.orders_file)
    
    def get_orders_by_user(self, user_id: int) -> List[Dict]:
        """获取用户的订单"""
        orders = self.get_orders()
        return [o for o in orders if o['user_id'] == user_id]

    def get_order_by_id(self, order_id: int) -> Optional[Dict]:
        """根据ID获取订单"""
        orders = self.get_orders()
        return next((o for o in orders if o['id'] == order_id), None)

    def save_order(self, order: Dict):
        """保存订单"""
        orders = self.get_orders()
        existing_index = next((i for i, o in enumerate(orders) if o['id'] == order['id']), None)

        if existing_index is not None:
            orders[existing_index] = order
        else:
            orders.append(order)

        self._write_json(self.orders_file, orders)
    
    def create_order(self, user_id: int, product_id: int, quantity: int, total_price: float) -> Dict:
        """创建新订单"""
        orders = self.get_orders()
        new_id = max([o['id'] for o in orders], default=0) + 1

        # 获取商品信息
        product = self.get_product_by_id(product_id)
        product_name = product['name'] if product else '未知商品'

        order = {
            'id': new_id,
            'user_id': user_id,
            'product_id': product_id,
            'product_name': product_name,
            'quantity': quantity,
            'total_price': total_price,
            'status': '未发货',  # 修改状态为未发货
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        self.save_order(order)
        return order

    def update_order_status(self, order_id: int, status: str) -> bool:
        """更新订单状态"""
        order = self.get_order_by_id(order_id)
        if order:
            order['status'] = status
            order['updated_at'] = datetime.now().isoformat()
            self.save_order(order)
            return True
        return False

    def deduct_user_balance(self, user_id: int, amount: float) -> bool:
        """从用户余额中扣款"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        if user['balance'] < amount:
            return False

        user['balance'] -= amount
        self.save_user(user)
        return True

    def update_order_payment_status(self, order_id: int, payment_method: str, status: str = '已支付'):
        """更新订单支付状态"""
        orders = self._read_json(self.orders_file)
        for order in orders:
            if order['id'] == order_id:
                order['payment_method'] = payment_method
                order['status'] = status
                order['paid_at'] = datetime.now().isoformat()
                self._write_json(self.orders_file, orders)
                return True
        return False

    # 店铺余额管理
    def get_shop_balance(self) -> float:
        """获取店铺余额"""
        try:
            with open(self.shop_balance_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('balance', 0.0)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0.0

    def update_shop_balance(self, amount: float):
        """更新店铺余额"""
        current_balance = self.get_shop_balance()
        new_balance = current_balance + amount
        
        with self.lock:
            with open(self.shop_balance_file, 'w', encoding='utf-8') as f:
                json.dump({"balance": new_balance}, f, ensure_ascii=False, indent=2)
        
        return new_balance

    # 购物车管理
    def get_cart_by_user_id(self, user_id: int) -> Optional[Dict]:
        """获取用户的购物车"""
        carts = self._read_json(self.carts_file)
        return next((c for c in carts if c['user_id'] == user_id), None)

    def create_or_update_cart(self, user_id: int, product_id: int, quantity: int, set_quantity: bool = False) -> Dict:
        """创建或更新购物车商品"""
        carts = self._read_json(self.carts_file)
        user_cart = self.get_cart_by_user_id(user_id)
        
        if not user_cart:
            user_cart = {
                'user_id': user_id,
                'items': [],
                'updated_at': datetime.now().isoformat()
            }
            carts.append(user_cart)
        
        # 查找是否已存在该商品
        existing_item = next((item for item in user_cart['items'] if item['product_id'] == product_id), None)
        
        if existing_item:
            if set_quantity:
                existing_item['quantity'] = quantity  # 设置特定数量
            else:
                existing_item['quantity'] += quantity  # 累加数量
        else:
            user_cart['items'].append({
                'product_id': product_id,
                'quantity': quantity,
                'added_at': datetime.now().isoformat()
            })
        
        user_cart['updated_at'] = datetime.now().isoformat()
        self._write_json(self.carts_file, carts)
        return user_cart

    def remove_from_cart(self, user_id: int, product_id: int) -> bool:
        """从购物车移除商品"""
        try:
            carts = self._read_json(self.carts_file)
            user_cart_index = next((i for i, c in enumerate(carts) if c['user_id'] == user_id), None)
            
            if user_cart_index is not None:
                user_cart = carts[user_cart_index]
                original_length = len(user_cart.get('items', []))
                user_cart['items'] = [item for item in user_cart.get('items', []) if item['product_id'] != product_id]
                
                if len(user_cart['items']) < original_length:
                    user_cart['updated_at'] = datetime.now().isoformat()
                    # 如果购物车为空，移除整个购物车
                    if not user_cart['items']:
                        carts.pop(user_cart_index)
                    self._write_json(self.carts_file, carts)
                    return True
            return False
        except Exception as e:
            return False

    def clear_cart(self, user_id: int) -> bool:
        """清空购物车"""
        carts = self._read_json(self.carts_file)
        user_cart = self.get_cart_by_user_id(user_id)
        
        if user_cart:
            carts = [c for c in carts if c['user_id'] != user_id]
            self._write_json(self.carts_file, carts)
            return True
        return False

    # 评价管理
    def add_review(self, order_id: int, product_id: int, user_id: int, rating: int, comment: str):
        """添加商品评价"""
        reviews = self._read_json('reviews.json')  # 需要创建新的数据文件
        
        review = {
            'id': len(reviews) + 1,
            'order_id': order_id,
            'product_id': product_id,
            'user_id': user_id,
            'rating': rating,
            'comment': comment,
            'created_at': datetime.now().isoformat()
        }
        
        reviews.append(review)
        self._write_json('reviews.json', reviews)
        return review

# 全局数据库实例
db = DatabaseManager()