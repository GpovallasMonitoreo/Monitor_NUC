from flask import Blueprint, render_template, request, jsonify
from src.services.supabase_service import SupabaseService 

bp = Blueprint('views', __name__)
db_service = SupabaseService()

# --- RUTAS PRINCIPALES ---
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
    """Dashboard General Financiero"""
    return render_template('dashboard_finanzas.html')

@bp.route('/techview/detail')
def techview_detail():
    """
    Dashboard individual por ubicación.
    Contiene: CAPEX, OPEX, Mantenimiento, Ciclo de Vida.
    """
    device_id = request.args.get('device_id', 'REF-01')
    return render_template('techview.html', device_id=device_id)

@bp.route('/techview/proposal')
def techview_proposal():
    """
    NUEVA SECCIÓN: Propuesta de Instalación.
    Para evaluar proyectos antes de que sean activos.
    """
    return render_template('proposal.html')

@bp.route('/api/techview/inventory')
def api_inventory_list():
    try:
        response = db_service.client.table("devices").select("device_id, pc_name, status, ip_address").execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
