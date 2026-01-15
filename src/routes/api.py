from flask import Blueprint, request, jsonify
import logging
from datetime import datetime
import src  # Acceso a variables globales (src.monitor, src.supabase)

logger = logging.getLogger(__name__)

bp = Blueprint('api', __name__, url_prefix='/api')

# ==========================================
# 1. REPORTES DE AGENTES (Ingesta)
# ==========================================
@bp.route('/report', methods=['POST'])
def receive_report():
    try:
        data = request.get_json()
        if not data: return jsonify({"status": "error", "message": "No JSON"}), 400

        device_id = data.get('mac_address') or data.get('pc_name')
        if not device_id: return jsonify({"status": "error", "message": "Missing ID"}), 400

        # Si el monitor está activo, le pasamos los datos
        if src.monitor:
            src.monitor.ingest_data(data)
            return jsonify({"status": "success", "handler": "monitor"}), 200
        
        # Fallback a escritura directa si el monitor falló
        elif src.supabase and hasattr(src.supabase, 'upsert_device_status'):
            src.supabase.upsert_device_status({
                "device_id": device_id,
                "pc_name": data.get('pc_name'),
                "status": data.get('status', 'online'),
                "ip_address": data.get('ip_address'),
                "last_seen": datetime.utcnow().isoformat()
            })
            return jsonify({"status": "success", "handler": "direct_db"}), 200

        return jsonify({"status": "error", "message": "System unavailable"}), 503
    except Exception as e:
        logger.error(f"Error report: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
# 2. DATOS PARA DASHBOARD
# ==========================================
@bp.route('/data', methods=['GET'])
def get_all_data():
    """Devuelve solo dispositivos ACTIVOS para el monitor"""
    try:
        if src.monitor:
            # Filtramos en memoria para no mostrar los dados de baja
            active_devices = {
                k: v for k, v in src.monitor.devices_state.items() 
                if v.get('status') != 'inactive'
            }
            return jsonify(active_devices)
        return jsonify({})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 3. BITÁCORA (LOGS) + AUTOMATIZACIÓN DE BAJAS
# ==========================================
@bp.route('/history/all', methods=['GET'])
def get_history():
    try:
        if src.supabase and hasattr(src.supabase, 'client'):
            # Obtenemos los últimos 200 logs
            response = src.supabase.client.table('logs')\
                .select('*')\
                .order('timestamp', desc=True)\
                .limit(200)\
                .execute()
            
            # Adaptador de campos para el Frontend
            history = []
            for item in response.data:
                history.append({
                    "device_id": item.get('device_id'),
                    "pc_name": item.get('pc_name'),
                    "action": item.get('action'),
                    "what": item.get('what'),
                    "desc": item.get('description'),
                    "req": item.get('requested_by'),
                    "exec": item.get('executed_by'),
                    # Convertimos a string "true"/"false" para facilitar JS
                    "solved": str(item.get('is_solved')).lower(), 
                    "timestamp": item.get('timestamp')
                })
            return jsonify(history)
        return jsonify([])
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return jsonify([])

@bp.route('/history/add', methods=['POST'])
def add_history():
    try:
        data = request.get_json()
        if not src.supabase:
            return jsonify({"status": "error", "message": "DB Offline"}), 503

        pc_name = data.get('pc_name')
        action = data.get('action', '')

        # 1. Guardar en Bitácora (Logs)
        payload = {
            "device_id": pc_name,
            "pc_name": pc_name,
            "action": action,
            "what": data.get('what'),
            "description": data.get('desc'),
            "requested_by": data.get('req'),
            "executed_by": data.get('exec'),
            "is_solved": data.get('solved') == 'true',
            "timestamp": datetime.utcnow().isoformat()
        }
        src.supabase.client.table('logs').insert(payload).execute()

        # 2. LÓGICA DE BAJA AUTOMÁTICA
        # Si la acción es dar de baja, actualizamos el inventario automáticamente
        action_lower = action.lower()
        if 'baja' in action_lower or 'retiro' in action_lower or 'descontinuado' in action_lower:
            logger.info(f"📉 Procesando BAJA automática para {pc_name}")
            
            # Actualizar tabla devices en Supabase
            src.supabase.client.table('devices').update({
                "status": "inactive",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("pc_name", pc_name).execute()
            
            # Actualizar memoria del monitor si está corriendo
            if src.monitor and pc_name in src.monitor.devices_state:
                src.monitor.devices_state[pc_name]['status'] = 'inactive'

        return jsonify({"status": "success", "message": "Log guardado"})

    except Exception as e:
        logger.error(f"Error saving log: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
