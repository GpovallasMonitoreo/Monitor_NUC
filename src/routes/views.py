from flask import Blueprint, render_template, request, jsonify
from src.services.supabase_service import SupabaseService 

bp = Blueprint('views', __name__)
db_service = SupabaseService()

# ... (RUTAS VIEJAS SE MANTIENEN IGUALES) ...

# ==========================================
# API TECHVIEW Y DASHBOARD
# ==========================================

@bp.route('/techview')
def techview_home():
    return render_template('dashboard_finanzas.html')

@bp.route('/techview/detail')
def techview_detail():
    device_id = request.args.get('device_id', 'REF-01')
    return render_template('techview.html', device_id=device_id)

@bp.route('/techview/proposal')
def techview_proposal():
    return render_template('proposal.html')

# --- APIS DE DATOS ---

@bp.route('/api/techview/dashboard')
def api_dashboard_data():
    """Datos globales: KPIs, Ventas Totales vs Costos"""
    data = db_service.get_financial_overview()
    if not data: return jsonify({"error": "No data"}), 500
    return jsonify(data)

@bp.route('/api/techview/device/<path:device_id>')
def api_device_detail(device_id):
    """Datos de una pantalla específica: CAPEX, OPEX, Tickets"""
    data = db_service.get_device_detail(device_id)
    if not data: return jsonify({"error": "Device not found"}), 404
    return jsonify(data)

@bp.route('/api/techview/inventory')
def api_inventory():
    """Lista para el buscador"""
    try:
        res = db_service.client.table("devices").select("device_id, pc_name, status, disconnect_count").execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/api/techview/save', methods=['POST'])
def api_save_financial():
    """Endpoint para guardar costos desde los formularios"""
    data = request.json
    success = db_service.save_financial_record(data)
    if success:
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 500
