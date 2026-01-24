from flask import Blueprint, render_template, request, jsonify
# Importamos el servicio de Supabase
from src.services.supabase_service import SupabaseService 

bp = Blueprint('views', __name__)
db_service = SupabaseService()

# --- RUTAS PRINCIPALES (PLATAFORMA MONITOREO) ---
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
# NUEVO MÓDULO: TECHVIEW (COSTOS)
# ==========================================

@bp.route('/techview')
def techview_home():
    """
    Ruta Principal de la nueva pestaña.
    Carga el Dashboard Financiero General (dashboard_finanzas.html).
    """
    return render_template('dashboard_finanzas.html')

@bp.route('/techview/detail')
def techview_detail():
    """
    Vista de Detalle por Pantalla.
    Carga la calculadora específica (techview.html).
    Ejemplo: /techview/detail?device_id=REF-01
    """
    device_id = request.args.get('device_id', 'REF-01')
    return render_template('techview.html', device_id=device_id)

@bp.route('/api/techview/inventory')
def api_inventory_list():
    """API para llenar tablas y buscadores con datos reales de Supabase"""
    try:
        response = db_service.client.table("devices").select("device_id, pc_name, status, ip_address").execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
