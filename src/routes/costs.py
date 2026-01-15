from flask import Blueprint, request, jsonify, render_template
import logging
from datetime import datetime
import src 

logger = logging.getLogger(__name__)

bp = Blueprint('costs', __name__, url_prefix='/costs')

# --- RUTAS DE NAVEGACIÓN (VISTAS) ---
@bp.route('/installations')
def view_installations():
    return render_template('costs/installations.html')

@bp.route('/maintenance')
def view_maintenance():
    return render_template('costs/maintenance.html')

@bp.route('/sales')
def view_sales():
    return render_template('costs/sales.html')

@bp.route('/dashboard')
def view_dashboard():
    return render_template('costs/dashboard.html')

# --- API: GUARDAR DATOS ---
@bp.route('/add', methods=['POST'])
def add_transaction():
    try:
        data = request.get_json()
        if not data.get('device_id') or not data.get('amount'):
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        payload = {
            "device_id": data.get('device_id'),
            "location": data.get('device_id'), # Usamos el ID como ubicación por defecto
            "type": data.get('type'),
            "subtype": data.get('subtype'),
            "description": data.get('description'),
            "amount": float(data.get('amount')),
            "date": data.get('date', datetime.now().strftime('%Y-%m-%d'))
        }

        src.supabase.client.table('finances').insert(payload).execute()
        return jsonify({"status": "success", "message": "Guardado"})
    except Exception as e:
        logger.error(f"Error finance: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API: REPORTE FINANCIERO (Lógica de Negocio) ---
@bp.route('/report', methods=['GET'])
def get_financial_report():
    try:
        response = src.supabase.client.table('finances').select('*').execute()
        transactions = response.data
        
        report = {}

        # 1. Sumarizar datos
        for t in transactions:
            dev = t.get('device_id')
            if dev not in report:
                report[dev] = {
                    "device_id": dev,
                    "cost_installation": 0.0,
                    "cost_maintenance": 0.0,
                    "total_sales": 0.0
                }
            
            amount = float(t['amount'])
            tipo = t['type']
            
            if tipo == 'installation':
                report[dev]['cost_installation'] += amount
            elif tipo == 'maintenance':
                report[dev]['cost_maintenance'] += amount
            elif tipo == 'sale':
                report[dev]['total_sales'] += amount

        # 2. Calcular ROI y Totales
        results = []
        for dev, data in report.items():
            total_expenses = data['cost_installation'] + data['cost_maintenance']
            net_profit = data['total_sales'] - total_expenses
            
            roi = 0
            status = "PÉRDIDA"
            
            if total_expenses > 0:
                roi = (data['total_sales'] / total_expenses) * 100
                if roi >= 100: status = "RENTABLE"
                elif roi > 50: status = "RECUPERANDO"
            elif data['total_sales'] > 0:
                status = "RENTABLE"
                roi = 100

            data['total_expenses'] = total_expenses
            data['net_profit'] = net_profit
            data['roi_percent'] = round(roi, 1)
            data['status_label'] = status
            
            results.append(data)

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
