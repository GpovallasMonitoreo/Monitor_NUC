from flask import Blueprint, render_template, request, jsonify
from src.services.supabase_service import SupabaseService 

bp = Blueprint('views', __name__)
db_service = SupabaseService()

# --- RUTAS PRINCIPALES (NO TOCAR) ---
@bp.route('/')
def home(): return render_template('index.html')
@bp.route('/monitor')
def monitor(): return render_template('monitor.html')
@bp.route('/latency')
def latency(): return render_template('latency.html')
@bp.route('/map')
def map_view(): return render_template('map.html')
@bp.route('/inventory')
def inventory_main(): return render_template('inventory/main.html')
@bp.route('/inventory/manuals')
def inventory_manuals(): return render_template('inventory/manuals.html')
@bp.route('/inventory/specs')
def inventory_specs(): return render_template('inventory/specs.html')
@bp.route('/inventory/logs')
def inventory_logs(): return render_template('inventory/logs.html')

# ==========================================
# MÓDULO TECHVIEW (COMPLETO)
# ==========================================

@bp.route('/techview')
def techview_home():
    """Dashboard General Financiero"""
    return render_template('dashboard_finanzas.html')

@bp.route('/techview/detail')
def techview_detail():
    """Formulario de Edición de Costos"""
    device_id = request.args.get('device_id', 'REF-01')
    return render_template('techview.html', device_id=device_id)

@bp.route('/techview/analysis')
def techview_analysis():
    """
    NUEVO: Dashboard Visual Premium (Site Analysis).
    """
    device_id = request.args.get('device_id', 'REF-01')
    return render_template('site_analysis.html', device_id=device_id)

@bp.route('/techview/proposal')
def techview_proposal():
    return render_template('proposal.html')

# --- API ENDPOINTS ---

@bp.route('/api/techview/dashboard')
def api_dashboard():
    data = db_service.get_financial_overview()
    if not data: return jsonify({"kpis": {}, "financials": {}})
    return jsonify(data)

@bp.route('/api/techview/device/<path:device_id>')
def api_device(device_id):
    data = db_service.get_device_detail(device_id)
    if not data: return jsonify({"totals": {}, "eco": {}})
    return jsonify(data)

@bp.route('/api/techview/inventory')
def api_inventory():
    try:
        res = db_service.client.table("devices").select("device_id, pc_name, status, ip_address").execute()
        return jsonify(res.data or [])
    except: return jsonify([])

@bp.route('/api/techview/save', methods=['POST'])
def api_save():
    success = db_service.save_cost_entry(request.json)
    if success: return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 500
