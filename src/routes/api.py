from flask import Blueprint, request, jsonify
import logging
from datetime import datetime
import src  # Acceso a las variables globales: src.monitor, src.supabase

logger = logging.getLogger(__name__)

bp = Blueprint('api', __name__, url_prefix='/api')

# ==========================================
# 1. REPORTES DE AGENTES (Ingesta de Datos)
# ==========================================
@bp.route('/report', methods=['POST'])
def receive_report():
    """Recibe datos de los agentes instalados en las PC."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data"}), 400

        device_id = data.get('mac_address') or data.get('pc_name')
        if not device_id:
            return jsonify({"status": "error", "message": "Missing ID"}), 400

        # A. Intentar pasar al MONITOR (Prioridad)
        if src.monitor:
            src.monitor.ingest_data(data)
            return jsonify({"status": "success", "handler": "monitor"}), 200
        
        # B. Fallback: Guardar directo en Supabase si el monitor falló
        elif src.supabase and hasattr(src.supabase, 'upsert_device_status'):
            logger.warning("⚠️ Monitor no disponible, guardando directo en DB")
            src.supabase.upsert_device_status({
                "device_id": device_id,
                "pc_name": data.get('pc_name'),
                "status": data.get('status', 'online'),
                "ip_address": data.get('ip_address'),
                "last_seen": datetime.utcnow().isoformat()
            })
            return jsonify({"status": "success", "handler": "direct_db"}), 200

        else:
            return jsonify({"status": "error", "message": "System unavailable"}), 503

    except Exception as e:
        logger.error(f"❌ Error procesando reporte: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/data', methods=['GET'])
def get_all_data():
    """Endpoint para el Dashboard (Datos en tiempo real)."""
    try:
        if src.monitor:
            # Devuelve lo que está en la memoria RAM del monitor
            return jsonify(src.monitor.devices_state)
        else:
            return jsonify({})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 2. BITÁCORA / HISTORIAL (Supabase)
# ==========================================
@bp.route('/history/all', methods=['GET'])
def get_history():
    """Obtiene los últimos logs de mantenimiento."""
    try:
        if src.supabase and hasattr(src.supabase, 'client'):
            # Consulta a la tabla 'logs'
            response = src.supabase.client.table('logs')\
                .select('*')\
                .order('timestamp', desc=True)\
                .limit(100)\
                .execute()
            
            # Adaptamos los datos para que el Frontend los entienda
            history = []
            for item in response.data:
                history.append({
                    "device_id": item.get('pc_name'), # Usamos pc_name para filtrar fácil en el front
                    "pc_name": item.get('pc_name'),
                    "action": item.get('action'),
                    "what": item.get('what'),
                    "desc": item.get('description'),
                    "req": item.get('requested_by'),
                    "exec": item.get('executed_by'),
                    "solved": str(item.get('is_solved')).lower(), # "true" / "false"
                    "timestamp": item.get('timestamp')
                })
            return jsonify(history)
        return jsonify([])
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return jsonify([])

@bp.route('/history/add', methods=['POST'])
def add_history():
    """Guarda un nuevo log de mantenimiento."""
    try:
        data = request.get_json()
        if not src.supabase:
            return jsonify({"status": "error", "message": "Database offline"}), 503

        # Preparar objeto para SQL
        payload = {
            "device_id": data.get('pc_name'),
            "pc_name": data.get('pc_name'),
            "action": data.get('action'),
            "what": data.get('what'),
            "description": data.get('desc'),
            "requested_by": data.get('req'),
            "executed_by": data.get('exec'),
            "is_solved": data.get('solved') == 'true', # Convertir string a boolean
            "timestamp": datetime.utcnow().isoformat()
        }

        # Insertar
        src.supabase.client.table('logs').insert(payload).execute()
        
        return jsonify({"status": "success", "message": "Log saved"})

    except Exception as e:
        logger.error(f"Error saving log: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
