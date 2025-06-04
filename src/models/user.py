from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='cliente')  # 'cliente' ou 'vendedor'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    subscription = db.relationship('Subscription', backref='user', lazy=True, uselist=False)
    qr_codes = db.relationship('QRCode', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='ativo')  # 'ativo', 'cancelado', 'expirado'
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    auto_renew = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    plan = db.relationship('Plan', backref='subscriptions', lazy=True)
    
    def __repr__(self):
        return f'<Subscription {self.id}>'

class Plan(db.Model):
    __tablename__ = 'plans'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    matte_quantity = db.Column(db.Integer, nullable=False)  # Quantidade de mattes por dia
    biscoito_quantity = db.Column(db.Integer, nullable=False)  # Quantidade de biscoitos Globo por dia
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Plan {self.name}>'

class QRCode(db.Model):
    __tablename__ = 'qr_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    code = db.Column(db.String(255), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    valid_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<QRCode {self.code}>'

class Redemption(db.Model):
    __tablename__ = 'redemptions'
    
    id = db.Column(db.Integer, primary_key=True)
    qr_code_id = db.Column(db.Integer, db.ForeignKey('qr_codes.id'), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    matte_quantity = db.Column(db.Integer, default=0)
    biscoito_quantity = db.Column(db.Integer, default=0)
    redeemed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    qr_code = db.relationship('QRCode', backref='redemptions', lazy=True)
    vendor = db.relationship('User', backref='redemptions', lazy=True)
    
    def __repr__(self):
        return f'<Redemption {self.id}>'

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)  # 'cartao' ou 'pix'
    status = db.Column(db.String(20), nullable=False, default='pendente')  # 'pendente', 'aprovado', 'recusado'
    transaction_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    subscription = db.relationship('Subscription', backref='payments', lazy=True)
    
    def __repr__(self):
        return f'<Payment {self.id}>'
