from flask import Blueprint, request, jsonify, session
from src.models.user import db, User, QRCode, Redemption, Subscription, Plan
from src.routes.auth import auth_required, vendor_required
from datetime import datetime, timedelta
import uuid
import qrcode
import io
import base64
import os

qrcode_bp = Blueprint('qrcode', __name__)

@qrcode_bp.route('/generate', methods=['GET'])
@auth_required
def generate_qrcode():
    """Gerar QR code para o usuário logado"""
    user_id = session['user_id']
    
    # Verificar se o usuário tem uma assinatura ativa
    subscription = Subscription.query.filter_by(user_id=user_id, status='ativo').first()
    if not subscription:
        return jsonify({'error': 'Você não possui uma assinatura ativa'}), 400
    
    # Verificar se o plano existe
    plan = Plan.query.get(subscription.plan_id)
    if not plan:
        return jsonify({'error': 'Plano não encontrado'}), 404
    
    # Verificar se já existe um QR code válido para hoje
    today = datetime.utcnow().date()
    tomorrow = today + timedelta(days=1)
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(tomorrow, datetime.min.time())
    
    existing_qrcode = QRCode.query.filter(
        QRCode.user_id == user_id,
        QRCode.created_at >= today_start,
        QRCode.created_at < today_end
    ).first()
    
    if existing_qrcode:
        # Verificar se já foi usado completamente
        redemptions = Redemption.query.filter_by(qr_code_id=existing_qrcode.id).all()
        
        total_matte_redeemed = sum(r.matte_quantity for r in redemptions)
        total_biscoito_redeemed = sum(r.biscoito_quantity for r in redemptions)
        
        # Se já usou tudo, gerar novo QR code
        if total_matte_redeemed >= plan.matte_quantity and total_biscoito_redeemed >= plan.biscoito_quantity:
            # Todos os produtos já foram resgatados hoje
            return jsonify({
                'error': 'Você já resgatou todos os produtos disponíveis para hoje',
                'matte_redeemed': total_matte_redeemed,
                'matte_total': plan.matte_quantity,
                'biscoito_redeemed': total_biscoito_redeemed,
                'biscoito_total': plan.biscoito_quantity
            }), 400
        
        # Retornar QR code existente com informações de uso
        qr_data = {
            'code': existing_qrcode.code,
            'valid_until': today_end.isoformat(),
            'matte_redeemed': total_matte_redeemed,
            'matte_remaining': plan.matte_quantity - total_matte_redeemed,
            'biscoito_redeemed': total_biscoito_redeemed,
            'biscoito_remaining': plan.biscoito_quantity - total_biscoito_redeemed
        }
        
        # Gerar imagem do QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(existing_qrcode.code)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Converter para base64
        buffered = io.BytesIO()
        img.save(buffered)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        qr_data['qr_image'] = f"data:image/png;base64,{img_str}"
        
        return jsonify(qr_data), 200
    
    # Criar novo QR code
    new_code = str(uuid.uuid4())
    valid_until = today_end
    
    new_qrcode = QRCode(
        user_id=user_id,
        code=new_code,
        valid_until=valid_until
    )
    
    db.session.add(new_qrcode)
    db.session.commit()
    
    # Gerar imagem do QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(new_code)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Converter para base64
    buffered = io.BytesIO()
    img.save(buffered)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({
        'code': new_code,
        'valid_until': valid_until.isoformat(),
        'matte_remaining': plan.matte_quantity,
        'biscoito_remaining': plan.biscoito_quantity,
        'qr_image': f"data:image/png;base64,{img_str}"
    }), 201

@qrcode_bp.route('/validate', methods=['POST'])
@vendor_required
def validate_qrcode():
    """Validar QR code e registrar retirada (apenas para vendedores)"""
    data = request.get_json()
    
    # Verificar se o código QR foi fornecido
    if 'code' not in data:
        return jsonify({'error': 'Código QR é obrigatório'}), 400
    
    # Verificar se as quantidades foram fornecidas
    if 'matte_quantity' not in data or 'biscoito_quantity' not in data:
        return jsonify({'error': 'Quantidades de matte e biscoito são obrigatórias'}), 400
    
    # Buscar QR code pelo código
    qrcode_obj = QRCode.query.filter_by(code=data['code']).first()
    
    if not qrcode_obj:
        return jsonify({'error': 'QR code inválido'}), 404
    
    # Verificar se o QR code ainda é válido
    now = datetime.utcnow()
    if qrcode_obj.valid_until and now > qrcode_obj.valid_until:
        return jsonify({'error': 'QR code expirado'}), 400
    
    # Buscar usuário e assinatura
    user = User.query.get(qrcode_obj.user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    subscription = Subscription.query.filter_by(user_id=user.id, status='ativo').first()
    if not subscription:
        return jsonify({'error': 'Usuário não possui assinatura ativa'}), 400
    
    plan = Plan.query.get(subscription.plan_id)
    if not plan:
        return jsonify({'error': 'Plano não encontrado'}), 404
    
    # Verificar resgates anteriores para hoje
    redemptions = Redemption.query.filter_by(qr_code_id=qrcode_obj.id).all()
    
    total_matte_redeemed = sum(r.matte_quantity for r in redemptions)
    total_biscoito_redeemed = sum(r.biscoito_quantity for r in redemptions)
    
    # Verificar se as quantidades solicitadas estão disponíveis
    matte_requested = int(data['matte_quantity'])
    biscoito_requested = int(data['biscoito_quantity'])
    
    matte_available = plan.matte_quantity - total_matte_redeemed
    biscoito_available = plan.biscoito_quantity - total_biscoito_redeemed
    
    if matte_requested > matte_available:
        return jsonify({
            'error': f'Quantidade de matte solicitada excede o disponível',
            'matte_available': matte_available,
            'matte_requested': matte_requested
        }), 400
    
    if biscoito_requested > biscoito_available:
        return jsonify({
            'error': f'Quantidade de biscoito solicitada excede o disponível',
            'biscoito_available': biscoito_available,
            'biscoito_requested': biscoito_requested
        }), 400
    
    # Registrar retirada
    vendor_id = session['user_id']
    
    new_redemption = Redemption(
        qr_code_id=qrcode_obj.id,
        vendor_id=vendor_id,
        matte_quantity=matte_requested,
        biscoito_quantity=biscoito_requested
    )
    
    db.session.add(new_redemption)
    db.session.commit()
    
    # Calcular quantidades restantes
    matte_remaining = matte_available - matte_requested
    biscoito_remaining = biscoito_available - biscoito_requested
    
    return jsonify({
        'message': 'Retirada registrada com sucesso',
        'redemption_id': new_redemption.id,
        'user': user.username,
        'plan': plan.name,
        'matte_redeemed': matte_requested,
        'matte_remaining': matte_remaining,
        'biscoito_redeemed': biscoito_requested,
        'biscoito_remaining': biscoito_remaining,
        'redeemed_at': new_redemption.redeemed_at.isoformat()
    }), 201

@qrcode_bp.route('/redemptions', methods=['GET'])
@vendor_required
def get_redemptions():
    """Obter histórico de retiradas (apenas para vendedores)"""
    # Parâmetros opcionais para filtrar por data
    date_str = request.args.get('date')
    
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Formato de data inválido. Use YYYY-MM-DD'}), 400
    else:
        target_date = datetime.utcnow().date()
    
    # Definir intervalo de datas
    start_date = datetime.combine(target_date, datetime.min.time())
    end_date = start_date + timedelta(days=1)
    
    # Buscar retiradas do vendedor logado
    vendor_id = session['user_id']
    
    redemptions = Redemption.query.filter(
        Redemption.vendor_id == vendor_id,
        Redemption.redeemed_at >= start_date,
        Redemption.redeemed_at < end_date
    ).order_by(Redemption.redeemed_at.desc()).all()
    
    redemption_list = []
    for redemption in redemptions:
        qrcode_obj = QRCode.query.get(redemption.qr_code_id)
        user = User.query.get(qrcode_obj.user_id) if qrcode_obj else None
        
        redemption_data = {
            'id': redemption.id,
            'user': user.username if user else 'Usuário não encontrado',
            'matte_quantity': redemption.matte_quantity,
            'biscoito_quantity': redemption.biscoito_quantity,
            'redeemed_at': redemption.redeemed_at.isoformat()
        }
        
        redemption_list.append(redemption_data)
    
    # Calcular totais
    total_matte = sum(r.matte_quantity for r in redemptions)
    total_biscoito = sum(r.biscoito_quantity for r in redemptions)
    
    return jsonify({
        'date': target_date.isoformat(),
        'total_redemptions': len(redemptions),
        'total_matte': total_matte,
        'total_biscoito': total_biscoito,
        'redemptions': redemption_list
    }), 200
