from flask import Blueprint, request, jsonify, render_template
import logging
from datetime import datetime
import src # Acceso a la instancia global de supabase

logger = logging.getLogger(__name__)

bp = Blueprint('costs', __name__, url_prefix='/costs')

# --- VISTAS ---
@bp.route('/')
def index():
    return render_template('costs.html')

# --- API: REGISTRAR MOVIMIENTO ---
@bp.route('/add', methods=['POST'])
def add_transaction():
    try:
        data = request.get_json()
        
        # Validaciones básicas
        if not data.get('device_id') or not data.get('amount'):
            return jsonify({"status": "error", "message": "Faltan datos obligatorios"}), 400

        payload = {
            "device_id": data.get('device_id'),
            "location": data.get('location'), # Se puede obtener autom. del dispositivo
            "type": data.get('type'),         # installation, maintenance, sale
            "subtype": data.get('subtype'),   # preventivo, correctivo, etc.
            "description": data.get('description'),
            "amount": float(data.get('amount')),
            "date": data.get('date', datetime.now().strftime('%Y-%m-%d'))
        }

        src.supabase.client.table('finances').insert(payload).execute()
        return jsonify({"status": "success", "message": "Movimiento registrado"})

    except Exception as e:
        logger.error(f"Error saving finance: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API: REPORTE DE RENTABILIDAD ---
@bp.route('/report', methods=['GET'])
def get_financial_report():
    try:
        # 1. Obtener todas las transacciones
        response = src.supabase.client.table('finances').select('*').execute()
        transactions = response.data
        
        report = {}

        # 2. Procesar datos en Python (Agregación)
        for t in transactions:
            dev = t.get('device_id')
            if dev not in report:
                report[dev] = {
                    "device_id": dev,
                    "location": t.get('location') or dev,
                    "cost_installation": 0.0,
                    "cost_maintenance": 0.0,
                    "total_sales": 0.0,
                    "history": [] # Para desglose si se requiere
                }
            
            amount = float(t['amount'])
            type_trans = t['type']
            
            if type_trans == 'installation':
                report[dev]['cost_installation'] += amount
            elif type_trans == 'maintenance':
                report[dev]['cost_maintenance'] += amount
            elif type_trans == 'sale':
                report[dev]['total_sales'] += amount

        # 3. Calcular Rentabilidad Final (ROI)
        results = []
        for dev, data in report.items():
            total_expenses = data['cost_installation'] + data['cost_maintenance']
            net_profit = data['total_sales'] - total_expenses
            
            # Estado de Rentabilidad
            status = "PÉRDIDA"
            roi_percent = 0
            if total_expenses > 0:
                roi_percent = (data['total_sales'] / total_expenses) * 100
                if roi_percent >= 100: status = "RENTABLE"
                elif roi_percent > 50: status = "RECUPERANDO"
            elif data['total_sales'] > 0:
                status = "RENTABLE" # Solo ventas, sin costos registrados
                roi_percent = 100

            data['total_expenses'] = total_expenses
            data['net_profit'] = net_profit
            data['roi_percent'] = round(roi_percent, 1)
            data['status_label'] = status
            
            results.append(data)

        return jsonify(results)

    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return jsonify({"error": str(e)}), 500
