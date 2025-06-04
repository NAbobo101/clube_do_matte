from flask import Blueprint, request, jsonify, session
from src.models.user import db, User, Redemption
from src.routes.auth import auth_required, vendor_required
from datetime import datetime, timedelta
import uuid

vendor_bp = Blueprint('vendor', __name__)

@vendor_bp.route('/register', methods=['POST'])
@auth_required
def register_vendor():
    """Registrar um novo vendedor (apenas para administradores)"""
    # Verificar se o usuário logado é um administrador
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Acesso restrito a administradores'}), 403
    
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
    
    # Criar novo vendedor
    from werkzeug.security import generate_password_hash
    hashed_password = generate_password_hash(data['password'])
    
    new_vendor = User(
        username=data['username'],
        email=data['email'],
        password=hashed_password,
        role='vendedor'
    )
    
    db.session.add(new_vendor)
    db.session.commit()
    
    return jsonify({
        'message': 'Vendedor registrado com sucesso',
        'vendor_id': new_vendor.id
    }), 201

@vendor_bp.route('/list', methods=['GET'])
@auth_required
def list_vendors():
    """Listar todos os vendedores (apenas para administradores)"""
    # Verificar se o usuário logado é um administrador
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Acesso restrito a administradores'}), 403
    
    vendors = User.query.filter_by(role='vendedor').all()
    
    vendor_list = []
    for vendor in vendors:
        vendor_data = {
            'id': vendor.id,
            'username': vendor.username,
            'email': vendor.email,
            'created_at': vendor.created_at.isoformat()
        }
        vendor_list.append(vendor_data)
    
    return jsonify(vendor_list), 200

@vendor_bp.route('/dashboard', methods=['GET'])
@vendor_required
def vendor_dashboard():
    """Obter dados do dashboard do vendedor"""
    vendor_id = session['user_id']
    
    # Obter data atual e intervalo para relatórios
    today = datetime.utcnow().date()
    start_of_today = datetime.combine(today, datetime.min.time())
    start_of_week = start_of_today - timedelta(days=today.weekday())
    start_of_month = datetime(today.year, today.month, 1)
    
    # Retiradas de hoje
    today_redemptions = Redemption.query.filter(
        Redemption.vendor_id == vendor_id,
        Redemption.redeemed_at >= start_of_today,
        Redemption.redeemed_at < start_of_today + timedelta(days=1)
    ).all()
    
    # Retiradas da semana
    week_redemptions = Redemption.query.filter(
        Redemption.vendor_id == vendor_id,
        Redemption.redeemed_at >= start_of_week,
        Redemption.redeemed_at < start_of_today + timedelta(days=1)
    ).all()
    
    # Retiradas do mês
    month_redemptions = Redemption.query.filter(
        Redemption.vendor_id == vendor_id,
        Redemption.redeemed_at >= start_of_month,
        Redemption.redeemed_at < start_of_today + timedelta(days=1)
    ).all()
    
    # Calcular totais
    today_matte = sum(r.matte_quantity for r in today_redemptions)
    today_biscoito = sum(r.biscoito_quantity for r in today_redemptions)
    
    week_matte = sum(r.matte_quantity for r in week_redemptions)
    week_biscoito = sum(r.biscoito_quantity for r in week_redemptions)
    
    month_matte = sum(r.matte_quantity for r in month_redemptions)
    month_biscoito = sum(r.biscoito_quantity for r in month_redemptions)
    
    # Dados para o gráfico diário (últimos 7 dias)
    daily_data = []
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = start_of_day + timedelta(days=1)
        
        day_redemptions = Redemption.query.filter(
            Redemption.vendor_id == vendor_id,
            Redemption.redeemed_at >= start_of_day,
            Redemption.redeemed_at < end_of_day
        ).all()
        
        day_matte = sum(r.matte_quantity for r in day_redemptions)
        day_biscoito = sum(r.biscoito_quantity for r in day_redemptions)
        
        daily_data.append({
            'date': target_date.isoformat(),
            'matte': day_matte,
            'biscoito': day_biscoito,
            'total_redemptions': len(day_redemptions)
        })
    
    return jsonify({
        'today': {
            'date': today.isoformat(),
            'total_redemptions': len(today_redemptions),
            'matte': today_matte,
            'biscoito': today_biscoito
        },
        'week': {
            'start_date': start_of_week.date().isoformat(),
            'end_date': today.isoformat(),
            'total_redemptions': len(week_redemptions),
            'matte': week_matte,
            'biscoito': week_biscoito
        },
        'month': {
            'start_date': start_of_month.date().isoformat(),
            'end_date': today.isoformat(),
            'total_redemptions': len(month_redemptions),
            'matte': month_matte,
            'biscoito': month_biscoito
        },
        'daily_chart': daily_data
    }), 200

@vendor_bp.route('/reports', methods=['GET'])
@auth_required
def vendor_reports():
    """Obter relatórios de vendedores (para administradores) ou do próprio vendedor"""
    user_id = session['user_id']
    user_role = session.get('user_role')
    
    # Parâmetros de filtro
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    vendor_id_str = request.args.get('vendor_id')
    
    # Converter datas
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            start_datetime = datetime.combine(start_date, datetime.min.time())
        else:
            # Padrão: início do mês atual
            today = datetime.utcnow().date()
            start_datetime = datetime(today.year, today.month, 1)
        
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            end_datetime = datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)
        else:
            # Padrão: data atual
            end_datetime = datetime.combine(datetime.utcnow().date(), datetime.min.time()) + timedelta(days=1)
    except ValueError:
        return jsonify({'error': 'Formato de data inválido. Use YYYY-MM-DD'}), 400
    
    # Filtrar por vendedor específico ou todos (apenas para admin)
    if user_role == 'admin':
        if vendor_id_str:
            try:
                vendor_id = int(vendor_id_str)
                # Verificar se o vendedor existe
                vendor = User.query.filter_by(id=vendor_id, role='vendedor').first()
                if not vendor:
                    return jsonify({'error': 'Vendedor não encontrado'}), 404
                
                vendors = [vendor]
            except ValueError:
                return jsonify({'error': 'ID de vendedor inválido'}), 400
        else:
            # Todos os vendedores
            vendors = User.query.filter_by(role='vendedor').all()
    else:
        # Vendedor só pode ver seus próprios relatórios
        vendors = [User.query.get(user_id)]
    
    # Gerar relatório
    report_data = []
    
    for vendor in vendors:
        # Buscar retiradas do vendedor no período
        redemptions = Redemption.query.filter(
            Redemption.vendor_id == vendor.id,
            Redemption.redeemed_at >= start_datetime,
            Redemption.redeemed_at < end_datetime
        ).order_by(Redemption.redeemed_at).all()
        
        # Calcular totais
        total_matte = sum(r.matte_quantity for r in redemptions)
        total_biscoito = sum(r.biscoito_quantity for r in redemptions)
        
        # Agrupar por dia
        daily_breakdown = {}
        for redemption in redemptions:
            day = redemption.redeemed_at.date().isoformat()
            if day not in daily_breakdown:
                daily_breakdown[day] = {
                    'matte': 0,
                    'biscoito': 0,
                    'redemptions': 0
                }
            
            daily_breakdown[day]['matte'] += redemption.matte_quantity
            daily_breakdown[day]['biscoito'] += redemption.biscoito_quantity
            daily_breakdown[day]['redemptions'] += 1
        
        # Converter para lista ordenada por data
        daily_list = [{'date': day, **data} for day, data in daily_breakdown.items()]
        daily_list.sort(key=lambda x: x['date'])
        
        vendor_report = {
            'vendor_id': vendor.id,
            'vendor_name': vendor.username,
            'period': {
                'start_date': start_datetime.date().isoformat(),
                'end_date': (end_datetime - timedelta(days=1)).date().isoformat()
            },
            'summary': {
                'total_redemptions': len(redemptions),
                'total_matte': total_matte,
                'total_biscoito': total_biscoito
            },
            'daily_breakdown': daily_list
        }
        
        report_data.append(vendor_report)
    
    # Se for relatório de um único vendedor, retornar diretamente
    if len(report_data) == 1:
        return jsonify(report_data[0]), 200
    
    # Caso contrário, retornar lista de relatórios
    return jsonify(report_data), 200
