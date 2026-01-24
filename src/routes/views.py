from flask import Blueprint, render_template, request, jsonify
from src.services.supabase_service import SupabaseService 

bp = Blueprint('views', __name__)
db_service = SupabaseService()

# ==========================================
# RUTAS ORIGINALES DE MONITOREO (NO BORRAR)
# ==========================================

@bp.route('/')
def home():
    return render_template('index.html') # O tu template principal

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
# MÓDULO TECHVIEW (FINANZAS & COSTOS)
# ==========================================

@bp.route('/techview')
def techview_home():
    """Dashboard General Financiero"""
    return render_template('dashboard_finanzas.html')

@bp.route('/techview/detail')
def techview_detail():
    """Detalle de una pantalla (Calculadora)"""
    device_id = request.args.get('device_id', 'REF-01')
    return render_template('techview.html', device_id=device_id)

@bp.route('/techview/proposal')
def techview_proposal():
    """Nueva Propuesta de Instalación"""
    return render_template('proposal.html')

# --- API ENDPOINTS (JSON) ---

@bp.route('/api/techview/dashboard')
def api_dashboard():
    """KPIs globales reales"""
    data = db_service.get_financial_overview()
    if data: return jsonify(data)
    return jsonify({"kpis": {"capex": 0, "sales": 0}, "financials": {}}), 200

@bp.route('/api/techview/device/<path:device_id>')
def api_device(device_id):
    """Datos financieros de un dispositivo"""
    data = db_service.get_device_financials(device_id)
    if data: return jsonify(data)
    return jsonify({"error": "No data"}), 404

@bp.route('/api/techview/inventory')
def api_inventory():
    """Lista de dispositivos para tablas y buscadores"""
    try:
        # Traemos datos técnicos básicos
        res = db_service.client.table("devices").select("device_id, pc_name, status, ip_address, disconnect_count").execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/api/techview/save', methods=['POST'])
def api_save():
    """Guardar costo en DB"""
    success = db_service.save_cost_entry(request.json)
    if success: return jsonify({"status": "saved"}), 200
    return jsonify({"status": "error"}), 500
