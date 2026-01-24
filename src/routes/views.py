from flask import Blueprint, render_template, request, jsonify
# Asegúrate de que esta importación apunte correctamente a tu archivo de servicio
from src.services.supabase_service import SupabaseService 

bp = Blueprint('views', __name__)
db_service = SupabaseService() # Instanciamos el servicio para usarlo en el API

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

# --- MÓDULO DE INVENTARIO (SIDEBAR) ---
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
# NUEVAS RUTAS PARA TECHVIEW (COSTOS)
# ==========================================

@bp.route('/techview')
def techview_dashboard():
    """
    Renderiza la plataforma independiente de Costos.
    Captura el parámetro ?device_id=XYZ de la URL para cargar datos dinámicos.
    """
    device_id = request.args.get('device_id', 'REF-01') # Default si no hay ID
    
    # Renderizamos la plantilla única, pasándole el ID que solicitó el usuario
    return render_template('techview.html', device_id=device_id)

@bp.route('/api/techview/inventory')
def api_inventory_list():
    """
    API JSON para llenar el buscador del modal en TechView.
    Retorna lista ligera de equipos desde Supabase.
    """
    try:
        # Consulta a Supabase: Trae ID, Nombre, Estado e IP
        response = db_service.client.table("devices").select("device_id, pc_name, status, ip_address").execute()
        return jsonify(response.data)
    except Exception as e:
        print(f"Error API Inventory: {e}")
        return jsonify({"error": str(e)}), 500
