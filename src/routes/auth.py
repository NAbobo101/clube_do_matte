from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from src.models.user import db, User, Subscription, Plan, QRCode
import datetime
import uuid

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Verificar se os campos obrigatórios estão presentes
    required_fields = ['username', 'email', 'password']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo {field} é obrigatório'}), 400
    
    # Verificar se o usuário ou email já existem
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Nome de usuário já existe'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email já está em uso'}), 400
    
    # Criar novo usuário
    role = data.get('role', 'cliente')  # Por padrão, o usuário é cliente
    
    # Apenas permitir criação de vendedores por administradores (implementar depois)
    if role == 'vendedor' and session.get('user_role') != 'admin':
        role = 'cliente'  # Força o papel para cliente se não for admin
    
    hashed_password = generate_password_hash(data['password'])
    
    new_user = User(
        username=data['username'],
        email=data['email'],
        password=hashed_password,
        role=role
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({
        'message': 'Usuário registrado com sucesso',
        'user_id': new_user.id
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    # Verificar se os campos obrigatórios estão presentes
    if 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Nome de usuário e senha são obrigatórios'}), 400
    
    # Buscar usuário pelo nome de usuário
    user = User.query.filter_by(username=data['username']).first()
    
    # Verificar se o usuário existe e a senha está correta
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'error': 'Nome de usuário ou senha inválidos'}), 401
    
    # Criar sessão para o usuário
    session['user_id'] = user.id
    session['username'] = user.username
    session['user_role'] = user.role
    
    return jsonify({
        'message': 'Login realizado com sucesso',
        'user_id': user.id,
        'username': user.username,
        'role': user.role
    }), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    # Limpar a sessão
    session.clear()
    return jsonify({'message': 'Logout realizado com sucesso'}), 200

@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    # Verificar se o usuário está logado
    if 'user_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401
    
    # Buscar usuário pelo ID da sessão
    user = User.query.get(session['user_id'])
    
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    # Buscar assinatura ativa do usuário
    subscription = Subscription.query.filter_by(user_id=user.id, status='ativo').first()
    
    # Preparar dados do perfil
    profile_data = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'created_at': user.created_at.isoformat(),
        'subscription': None
    }
    
    # Adicionar dados da assinatura se existir
    if subscription:
        plan = Plan.query.get(subscription.plan_id)
        profile_data['subscription'] = {
            'id': subscription.id,
            'plan_name': plan.name,
            'plan_description': plan.description,
            'matte_quantity': plan.matte_quantity,
            'biscoito_quantity': plan.biscoito_quantity,
            'start_date': subscription.start_date.isoformat(),
            'end_date': subscription.end_date.isoformat() if subscription.end_date else None,
            'auto_renew': subscription.auto_renew,
            'status': subscription.status
        }
    
    return jsonify(profile_data), 200

# Middleware para verificar autenticação
def auth_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Não autorizado'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Middleware para verificar se o usuário é vendedor
def vendor_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Não autorizado'}), 401
        if session.get('user_role') != 'vendedor':
            return jsonify({'error': 'Acesso restrito a vendedores'}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function
