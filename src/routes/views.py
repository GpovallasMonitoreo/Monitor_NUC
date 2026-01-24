from flask import Blueprint, render_template, request, jsonify
from src.services.supabase_service import SupabaseService 

bp = Blueprint('views', __name__)
db_service = SupabaseService()

# --- RUTAS PRINCIPALES DEL MONITOR (NO BORRAR) ---
@bp.route('/')
def home():
    return render_template('index.html')

@bp.route('/monitor')
def monitor():
    return render_template('monitor.html')

@bp.route('/latency')
def latency():
    return render_template('latency.html')

@bp.route('/map')
def map_view():
    return render_template('map.html')

# --- MÓDULO DE INVENTARIO ---
@bp.route('/inventory')
def inventory_main():
    return render_template('inventory/main.html')

@bp.route('/inventory/manuals')
def inventory_manuals():
    return render_template('inventory/manuals.html')

@bp.route('/inventory/specs')
def inventory_specs():
    return render_template('inventory/specs.html')

@bp.route('/inventory/logs')
def inventory_logs():
    return render_template('inventory/logs.html')

# ==========================================
# MÓDULO TECHVIEW (COSTOS & FINANZAS)
# ==========================================

@bp.route('/techview')
def techview_home():
    """Dashboard General"""
    return render_template('dashboard_finanzas.html')

@bp.route('/techview/detail')
def techview_detail():
    """Calculadora por Pantalla"""
    device_id = request.args.get('device_id', 'REF-01')
    return render_template('techview.html', device_id=device_id)

@bp.route('/techview/proposal')
def techview_proposal():
    """Nueva Propuesta"""
    return render_template('proposal.html')

# --- API ENDPOINTS (JSON) ---

@bp.route('/api/techview/dashboard')
def api_dashboard():
    """Datos para el Dashboard Principal"""
    data = db_service.get_financial_overview()
    # Siempre devolver JSON, incluso si es vacío, para evitar Error 500 en frontend
    if not data:
        return jsonify({
            "kpis": {"capex": 0, "sales_annual": 0, "opex_monthly": 0, "incidents": 0, "active_alerts": 0},
            "financials": {"months": [], "sales": [], "maintenance": []}
        })
    return jsonify(data)

@bp.route('/api/techview/device/<path:device_id>')
def api_device(device_id):
    """Datos detallados de dispositivo"""
    data = db_service.get_device_financials(device_id)
    if not data: return jsonify({"breakdown": [], "totals": {}})
    return jsonify(data)

@bp.route('/api/techview/inventory')
def api_inventory():
    """Lista de dispositivos para el buscador"""
    try:
        res = db_service.client.table("devices").select("device_id, pc_name, status, ip_address").execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify([]) # Retornar lista vacía en error

@bp.route('/api/techview/save', methods=['POST'])
def api_save():
    """Guardar cambios"""
    success = db_service.save_cost_entry(request.json)
    if success: return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 500
