from flask import Blueprint, request, jsonify, render_template
import logging
from datetime import datetime
import src # Acceso a supabase

logger = logging.getLogger(__name__)

bp = Blueprint('costs', __name__, url_prefix='/costs')

# 1. RENDERIZAR LA VISTA HTML
@bp.route('/')
def index():
    return render_template('costs.html')

# 2. API: GUARDAR TRANSACCIÓN (Gasto o Venta)
@bp.route('/add', methods=['POST'])
def add_transaction():
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        category = data.get('category')
        amount = float(data.get('amount', 0))
        
        # SI ES GASTO (Instalación o Mantenimiento), LO GUARDAMOS NEGATIVO
        # SI ES VENTA, LO GUARDAMOS POSITIVO
        if category in ['instalacion', 'mantenimiento_prev', 'mantenimiento_corr']:
            final_amount = -abs(amount) # Asegurar que sea negativo
        else:
            final_amount = abs(amount)  # Venta siempre positiva

        payload = {
            "device_id": device_id,
            "location": data.get('location'),
            "category": category,
            "concept": data.get('concept'),
            "amount": final_amount,
            "transaction_date": data.get('date', datetime.now().strftime('%Y-%m-%d'))
        }

        src.supabase.client.table('finances').insert(payload).execute()
        return jsonify({"status": "success", "message": "Transacción registrada"})
    except Exception as e:
        logger.error(f"Error finance: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 3. API: REPORTE FINANCIERO POR UBICACIÓN
@bp.route('/summary', methods=['GET'])
def get_financial_summary():
    try:
        # Traer todas las transacciones
        response = src.supabase.client.table('finances').select('*').execute()
        transactions = response.data
        
        # Agrupar por Dispositivo/Ubicación
        summary = {}
        
        for t in transactions:
            dev_id = t['device_id'] or 'Desconocido'
            loc = t['location'] or dev_id
            
            if dev_id not in summary:
                summary[dev_id] = {
                    "device_id": dev_id,
                    "location": loc,
                    "investment": 0,    # Instalación
                    "maintenance": 0,   # Mantenimientos
                    "revenue": 0,       # Ventas
                    "total_balance": 0, # Ganancia Neta
                    "history": []
                }
            
            amt = float(t['amount'])
            cat = t['category']
            
            # Acumuladores
            if cat == 'instalacion':
                summary[dev_id]['investment'] += abs(amt)
            elif 'mantenimiento' in cat:
                summary[dev_id]['maintenance'] += abs(amt)
            elif cat == 'venta':
                summary[dev_id]['revenue'] += amt
                
            summary[dev_id]['total_balance'] += amt
            summary[dev_id]['history'].append(t)

        # Calcular Rentabilidad y ROI
        results = []
        for key, data in summary.items():
            total_cost = data['investment'] + data['maintenance']
            profit = data['revenue'] - total_cost
            
            # Punto de Equilibrio (ROI %)
            roi = 0
            if total_cost > 0:
                roi = (data['revenue'] / total_cost) * 100
                
            status = "PÉRDIDA"
            if roi >= 100: status = "RENTABLE"
            elif roi > 50: status = "RECUPERANDO"
            
            data['roi'] = round(roi, 1)
            data['status_label'] = status
            results.append(data)

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
