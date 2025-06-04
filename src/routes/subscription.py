from flask import Blueprint, request, jsonify, session
from src.models.user import db, Plan, Subscription, Payment, User
from src.routes.auth import auth_required
from datetime import datetime, timedelta
import uuid

subscription_bp = Blueprint('subscription', __name__)

@subscription_bp.route('/plans', methods=['GET'])
def get_plans():
    """Obter todos os planos disponíveis"""
    plans = Plan.query.all()
    plans_data = []
    
    for plan in plans:
        plans_data.append({
            'id': plan.id,
            'name': plan.name,
            'description': plan.description,
            'price': plan.price,
            'matte_quantity': plan.matte_quantity,
            'biscoito_quantity': plan.biscoito_quantity
        })
    
    return jsonify(plans_data), 200

@subscription_bp.route('/subscribe', methods=['POST'])
@auth_required
def subscribe():
    """Assinar um plano"""
    data = request.get_json()
    
    # Verificar se o plano_id foi fornecido
    if 'plan_id' not in data:
        return jsonify({'error': 'ID do plano é obrigatório'}), 400
    
    # Verificar se o método de pagamento foi fornecido
    if 'payment_method' not in data:
        return jsonify({'error': 'Método de pagamento é obrigatório'}), 400
    
    # Verificar se o método de pagamento é válido
    if data['payment_method'] not in ['cartao', 'pix']:
        return jsonify({'error': 'Método de pagamento inválido. Use "cartao" ou "pix"'}), 400
    
    # Buscar o plano pelo ID
    plan = Plan.query.get(data['plan_id'])
    if not plan:
        return jsonify({'error': 'Plano não encontrado'}), 404
    
    # Verificar se o usuário já tem uma assinatura ativa
    user_id = session['user_id']
    active_subscription = Subscription.query.filter_by(user_id=user_id, status='ativo').first()
    
    if active_subscription:
        return jsonify({'error': 'Você já possui uma assinatura ativa'}), 400
    
    # Criar nova assinatura
    end_date = datetime.utcnow() + timedelta(days=30)  # Assinatura válida por 30 dias
    new_subscription = Subscription(
        user_id=user_id,
        plan_id=plan.id,
        status='ativo',
        start_date=datetime.utcnow(),
        end_date=end_date,
        auto_renew=True
    )
    
    db.session.add(new_subscription)
    db.session.flush()  # Para obter o ID da assinatura
    
    # Criar registro de pagamento
    transaction_id = str(uuid.uuid4())
    new_payment = Payment(
        subscription_id=new_subscription.id,
        amount=plan.price,
        payment_method=data['payment_method'],
        status='aprovado',  # Simulando pagamento aprovado
        transaction_id=transaction_id
    )
    
    db.session.add(new_payment)
    db.session.commit()
    
    return jsonify({
        'message': 'Assinatura realizada com sucesso',
        'subscription_id': new_subscription.id,
        'plan_name': plan.name,
        'amount': plan.price,
        'payment_method': data['payment_method'],
        'transaction_id': transaction_id,
        'valid_until': end_date.isoformat()
    }), 201

@subscription_bp.route('/cancel', methods=['POST'])
@auth_required
def cancel_subscription():
    """Cancelar assinatura ativa"""
    user_id = session['user_id']
    
    # Buscar assinatura ativa do usuário
    subscription = Subscription.query.filter_by(user_id=user_id, status='ativo').first()
    
    if not subscription:
        return jsonify({'error': 'Você não possui uma assinatura ativa'}), 404
    
    # Cancelar assinatura
    subscription.status = 'cancelado'
    subscription.auto_renew = False
    db.session.commit()
    
    return jsonify({
        'message': 'Assinatura cancelada com sucesso',
        'subscription_id': subscription.id
    }), 200

@subscription_bp.route('/renew', methods=['POST'])
@auth_required
def toggle_auto_renew():
    """Ativar/desativar renovação automática"""
    data = request.get_json()
    user_id = session['user_id']
    
    # Verificar se o parâmetro auto_renew foi fornecido
    if 'auto_renew' not in data:
        return jsonify({'error': 'Parâmetro auto_renew é obrigatório'}), 400
    
    # Buscar assinatura ativa do usuário
    subscription = Subscription.query.filter_by(user_id=user_id, status='ativo').first()
    
    if not subscription:
        return jsonify({'error': 'Você não possui uma assinatura ativa'}), 404
    
    # Atualizar configuração de renovação automática
    subscription.auto_renew = bool(data['auto_renew'])
    db.session.commit()
    
    return jsonify({
        'message': 'Configuração de renovação automática atualizada',
        'subscription_id': subscription.id,
        'auto_renew': subscription.auto_renew
    }), 200

@subscription_bp.route('/history', methods=['GET'])
@auth_required
def payment_history():
    """Obter histórico de pagamentos do usuário"""
    user_id = session['user_id']
    
    # Buscar todas as assinaturas do usuário
    subscriptions = Subscription.query.filter_by(user_id=user_id).all()
    
    if not subscriptions:
        return jsonify([]), 200
    
    # Coletar IDs das assinaturas
    subscription_ids = [sub.id for sub in subscriptions]
    
    # Buscar pagamentos relacionados às assinaturas
    payments = Payment.query.filter(Payment.subscription_id.in_(subscription_ids)).order_by(Payment.created_at.desc()).all()
    
    payment_history = []
    for payment in payments:
        subscription = next((sub for sub in subscriptions if sub.id == payment.subscription_id), None)
        plan = Plan.query.get(subscription.plan_id) if subscription else None
        
        payment_data = {
            'id': payment.id,
            'amount': payment.amount,
            'payment_method': payment.payment_method,
            'status': payment.status,
            'transaction_id': payment.transaction_id,
            'created_at': payment.created_at.isoformat(),
            'plan_name': plan.name if plan else 'Plano não encontrado',
            'subscription_status': subscription.status if subscription else 'N/A'
        }
        
        payment_history.append(payment_data)
    
    return jsonify(payment_history), 200
