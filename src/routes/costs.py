from flask import Blueprint, request, jsonify, render_template
import logging
from datetime import datetime
import src # Acceso a la instancia global de supabase

logger = logging.getLogger(__name__)

bp = Blueprint('costs', __name__, url_prefix='/costs')

# ==============================================================================
# 1. RUTAS DE VISTAS (LAS 4 PANTALLAS INDEPENDIENTES)
# ==============================================================================

@bp.route('/installations')
def view_installations():
    """Pantalla 1: Formulario de Instalaciones"""
    return render_template('costs/installations.html')

@bp.route('/maintenance')
def view_maintenance():
    """Pantalla 2: Formulario de Mantenimiento"""
    return render_template('costs/maintenance.html')

@bp.route('/sales')
def view_sales():
    """Pantalla 3: Formulario de Ventas"""
    return render_template('costs/sales.html')

@bp.route('/dashboard')
def view_dashboard():
    """Pantalla 4: Costo por Ubicación (Reporte Final)"""
    return render_template('costs/dashboard.html')


# ==============================================================================
# 2. API: GUARDAR INFORMACIÓN (Ingresos y Egresos)
# ==============================================================================
@bp.route('/add', methods=['POST'])
def add_transaction():
    try:
        data = request.get_json()
        
        # Validaciones
        if not data.get('device_id') or not data.get('amount'):
            return jsonify({"status": "error", "message": "Faltan datos obligatorios"}), 400

        payload = {
            "device_id": data.get('device_id'),
            "location": data.get('location'), 
            "type": data.get('type'),         # 'installation', 'maintenance', 'sale'
            "subtype": data.get('subtype'),   # 'preventivo', 'correctivo', 'material'
            "description": data.get('description'),
            "amount": float(data.get('amount')),
            "date": data.get('date', datetime.now().strftime('%Y-%m-%d'))
        }

        src.supabase.client.table('finances').insert(payload).execute()
        return jsonify({"status": "success", "message": "Registro guardado correctamente"})

    except Exception as e:
        logger.error(f"Error saving finance: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ==============================================================================
# 3. API: REPORTE FINANCIERO (Lógica de Costo por Ubicación)
# ==============================================================================
@bp.route('/report', methods=['GET'])
def get_financial_report():
    try:
        # Traer todas las transacciones de Supabase
        response = src.supabase.client.table('finances').select('*').execute()
        transactions = response.data
        
        report = {}

        # Agrupar por dispositivo (Ubicación)
        for t in transactions:
            dev = t.get('device_id')
            if dev not in report:
                report[dev] = {
                    "device_id": dev,
                    "location": t.get('location') or dev,
                    "cost_installation": 0.0,
                    "cost_maintenance": 0.0,
                    "total_sales": 0.0
                }
            
            amount = float(t['amount'])
            type_trans = t['type']
            
            # Sumar según categoría
            if type_trans == 'installation':
                report[dev]['cost_installation'] += amount
            elif type_trans == 'maintenance':
                report[dev]['cost_maintenance'] += amount
            elif type_trans == 'sale':
                report[dev]['total_sales'] += amount

        # Calcular totales y ROI final
        results = []
        for dev, data in report.items():
            # Suma de los dos anteriores (Instalación + Mantenimiento)
            total_expenses = data['cost_installation'] + data['cost_maintenance']
            
            # Ganancia o Pérdida Neta
            net_profit = data['total_sales'] - total_expenses
            
            # Cálculo de ROI y Punto de Equilibrio
            roi_percent = 0
            status = "PÉRDIDA"
            
            if total_expenses > 0:
                roi_percent = (data['total_sales'] / total_expenses) * 100
                if roi_percent >= 100: status = "RENTABLE"
                elif roi_percent > 50: status = "RECUPERANDO"
            elif data['total_sales'] > 0:
                status = "RENTABLE" # Solo ganancia
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
