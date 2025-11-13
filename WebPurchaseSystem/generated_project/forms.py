from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FloatField, IntegerField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, NumberRange, Email, EqualTo, ValidationError
import re

class LoginForm(FlaskForm):
    """登录表单"""
    username = StringField('用户名', validators=[
        DataRequired(message='用户名不能为空'),
        Length(min=3, max=20, message='用户名长度必须在3-20个字符之间')
    ])
    password = PasswordField('密码', validators=[
        DataRequired(message='密码不能为空'),
        Length(min=6, max=128, message='密码长度必须在6-128个字符之间')
    ])

class RegisterForm(FlaskForm):
    """注册表单"""
    username = StringField('用户名', validators=[
        DataRequired(message='用户名不能为空'),
        Length(min=3, max=20, message='用户名长度必须在3-20个字符之间')
    ])
    password = PasswordField('密码', validators=[
        DataRequired(message='密码不能为空'),
        Length(min=6, max=128, message='密码长度必须在6-128个字符之间')
    ])
    confirm_password = PasswordField('确认密码', validators=[
        DataRequired(message='确认密码不能为空'),
        EqualTo('password', message='两次输入的密码不一致')
    ])
    
    def validate_username(self, username):
        """验证用户名格式"""
        if not re.match(r'^[a-zA-Z0-9_]+$', username.data):
            raise ValidationError('用户名只能包含字母、数字和下划线')

class ProductForm(FlaskForm):
    """商品表单"""
    name = StringField('商品名称', validators=[
        DataRequired(message='商品名称不能为空'),
        Length(min=1, max=100, message='商品名称长度必须在1-100个字符之间')
    ])
    price = FloatField('价格', validators=[
        DataRequired(message='价格不能为空'),
        NumberRange(min=0.01, max=999999.99, message='价格必须在0.01-999999.99之间')
    ])
    stock = IntegerField('库存数量', validators=[
        DataRequired(message='库存数量不能为空'),
        NumberRange(min=0, max=999999, message='库存数量必须在0-999999之间')
    ])
    category = SelectField('分类', choices=[
        ('电子产品', '电子产品'),
        ('服装', '服装'),
        ('家居', '家居'),
        ('食品', '食品'),
        ('图书', '图书'),
        ('其他', '其他')
    ], validators=[DataRequired(message='请选择商品分类')])
    description = TextAreaField('商品描述', validators=[
        Length(max=500, message='商品描述不能超过500个字符')
    ])

class RechargeForm(FlaskForm):
    """充值表单"""
    amount = FloatField('充值金额', validators=[
        DataRequired(message='充值金额不能为空'),
        NumberRange(min=0.01, max=10000, message='充值金额必须在0.01-10000之间')
    ])

class AddressForm(FlaskForm):
    """地址表单"""
    province = StringField('省份', validators=[
        DataRequired(message='省份不能为空'),
        Length(min=1, max=50, message='省份长度必须在1-50个字符之间')
    ])
    city = StringField('城市', validators=[
        DataRequired(message='城市不能为空'),
        Length(min=1, max=50, message='城市长度必须在1-50个字符之间')
    ])
    district = StringField('区县', validators=[
        DataRequired(message='区县不能为空'),
        Length(min=1, max=50, message='区县长度必须在1-50个字符之间')
    ])
    detail = TextAreaField('详细地址', validators=[
        DataRequired(message='详细地址不能为空'),
        Length(min=1, max=200, message='详细地址长度必须在1-200个字符之间')
    ])
    phone = StringField('手机号', validators=[
        DataRequired(message='手机号不能为空'),
        Length(min=11, max=11, message='手机号必须是11位数字')
    ])
    
    def validate_phone(self, phone):
        """验证手机号格式"""
        if not re.match(r'^1[3-9]\d{9}$', phone.data):
            raise ValidationError('请输入正确的手机号格式')

class BuyProductForm(FlaskForm):
    quantity = IntegerField('购买数量', validators=[
        DataRequired(message='购买数量不能为空'),
        NumberRange(min=1, max=999, message='购买数量必须在1-999之间')
    ])
    payment_method = SelectField('付款方式', choices=[
        ('balance', '余额支付'),
        ('other', '其他支付方式')  # 可根据需要扩展
    ], default='balance', validators=[DataRequired(message='请选择付款方式')])
