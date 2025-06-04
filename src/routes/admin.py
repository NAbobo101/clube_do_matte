from flask import Blueprint, request, jsonify, session
from src.models.user import db, User, Plan

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/create_plan', methods=['POST'])
def create_plan():
    """Criar um novo plano (apenas para administradores)"""
    # Verificar se o usuário logado é um administrador
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Acesso restrito a administradores'}), 403
    
    data = request.get_json()
    
    # Verificar se os campos obrigatórios estão presentes
    required_fields = ['name', 'price', 'matte_quantity', 'biscoito_quantity']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo {field} é obrigatório'}), 400
    
    # Criar novo plano
    new_plan = Plan(
        name=data['name'],
        description=data.get('description', ''),
        price=float(data['price']),
        matte_quantity=int(data['matte_quantity']),
        biscoito_quantity=int(data['biscoito_quantity'])
    )
    
    db.session.add(new_plan)
    db.session.commit()
    
    return jsonify({
        'message': 'Plano criado com sucesso',
        'plan_id': new_plan.id
    }), 201

@admin_bp.route('/update_plan/<int:plan_id>', methods=['PUT'])
def update_plan(plan_id):
    """Atualizar um plano existente (apenas para administradores)"""
    # Verificar se o usuário logado é um administrador
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Acesso restrito a administradores'}), 403
    
    plan = Plan.query.get(plan_id)
    if not plan:
        return jsonify({'error': 'Plano não encontrado'}), 404
    
    data = request.get_json()
    
    # Atualizar campos
    if 'name' in data:
        plan.name = data['name']
    
    if 'description' in data:
        plan.description = data['description']
    
    if 'price' in data:
        plan.price = float(data['price'])
    
    if 'matte_quantity' in data:
        plan.matte_quantity = int(data['matte_quantity'])
    
    if 'biscoito_quantity' in data:
        plan.biscoito_quantity = int(data['biscoito_quantity'])
    
    db.session.commit()
    
    return jsonify({
        'message': 'Plano atualizado com sucesso',
        'plan': {
            'id': plan.id,
            'name': plan.name,
            'description': plan.description,
            'price': plan.price,
            'matte_quantity': plan.matte_quantity,
            'biscoito_quantity': plan.biscoito_quantity
        }
    }), 200

@admin_bp.route('/delete_plan/<int:plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    """Excluir um plano (apenas para administradores)"""
    # Verificar se o usuário logado é um administrador
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Acesso restrito a administradores'}), 403
    
    plan = Plan.query.get(plan_id)
    if not plan:
        return jsonify({'error': 'Plano não encontrado'}), 404
    
    db.session.delete(plan)
    db.session.commit()
    
    return jsonify({
        'message': 'Plano excluído com sucesso'
    }), 200

@admin_bp.route('/promote_to_admin/<int:user_id>', methods=['POST'])
def promote_to_admin(user_id):
    """Promover um usuário para administrador (apenas para administradores)"""
    # Verificar se o usuário logado é um administrador
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Acesso restrito a administradores'}), 403
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    user.role = 'admin'
    db.session.commit()
    
    return jsonify({
        'message': 'Usuário promovido a administrador com sucesso',
        'user_id': user.id,
        'username': user.username,
        'role': user.role
    }), 200

@admin_bp.route('/create_first_admin', methods=['POST'])
def create_first_admin():
    """Criar o primeiro administrador (apenas se não houver nenhum)"""
    # Verificar se já existe algum administrador
    admin_exists = User.query.filter_by(role='admin').first()
    if admin_exists:
        return jsonify({'error': 'Já existe pelo menos um administrador no sistema'}), 400
    
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
    
    # Criar novo administrador
    from werkzeug.security import generate_password_hash
    hashed_password = generate_password_hash(data['password'])
    
    new_admin = User(
        username=data['username'],
        email=data['email'],
        password=hashed_password,
        role='admin'
    )
    
    db.session.add(new_admin)
    db.session.commit()
    
    return jsonify({
        'message': 'Primeiro administrador criado com sucesso',
        'admin_id': new_admin.id
    }), 201
