import sys
import os
from flask import Blueprint, request, jsonify
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# Configuración rutas
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

# Importamos src para acceder a las variables globales (storage, appsheet, monitor)
import src 

# Definimos el Blueprint PRIMERO
bp = Blueprint('api', __name__, url_prefix='/api')

TZ_CDMX = ZoneInfo("America/Mexico_City")
EMAIL_TIMEOUT_SECONDS = 45 

# ================= RUTAS CORE =================

@bp.route('/report', methods=['POST'])
def report():
    """Recibe datos de NUCs"""
    try:
        data = request.get_json()
        if not data or 'pc_name' not in data:
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        now = datetime.now(TZ_CDMX)
        data['timestamp'] = now.isoformat()
        
        # 1. Storage Local
        if src.storage:
            src.storage.save_device_report(data)
        
        # 2. Monitor AppSheet (Si está activo)
        if src.monitor and src.appsheet.enabled:
            src.monitor.ingest_data(data.copy())
        
        return jsonify({"status": "OK"})

    except Exception as e:
        print(f"Error en /report: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/data', methods=['GET'])
def get_data():
    """Datos para el Dashboard"""
    try:
        if not src.storage: return jsonify({})

        raw_data = src.storage.get_all_devices()
        processed_data = {}
        now = datetime.now(TZ_CDMX)

        for pc_name, info in raw_data.items():
            device_info = info.copy()
            last_seen_str = info.get('timestamp')
            is_offline = True 

            if last_seen_str:
                try:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    if (now - last_seen).total_seconds() < EMAIL_TIMEOUT_SECONDS:
                        is_offline = False
                except ValueError: pass
            
            if is_offline:
                device_info['status'] = 'offline'
                alert_state = src.storage.alert_states.get(pc_name, {})
                if not alert_state.get('email_sent', False):
                    if src.alerts:
                        src.alerts.send_offline_alert(pc_name, info)
                    src.storage.alert_states[pc_name] = {'status': 'offline', 'email_sent': True}
            else:
                device_info['status'] = 'online'

            processed_data[pc_name] = device_info

        return jsonify(processed_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================= RUTAS APPSHEET =================

@bp.route('/appsheet/status', methods=['GET'])
def appsheet_status():
    """Estado de conexión para el frontend"""
    try:
        # Si src.appsheet es None (no se inicializó en app.py), devolvemos error controlado
        if not src.appsheet:
            return jsonify({
                "status": "disabled",
                "message": "Servicio no inicializado en servidor",
                "available": False
            }), 200 # Retornamos 200 para que el frontend pueda leer el JSON

        status_info = src.appsheet.get_status_info()
        
        if src.monitor:
            status_info['monitor_running'] = src.monitor.running
        else:
            status_info['monitor_running'] = False
            
        return jsonify(status_info), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/appsheet/sync', methods=['POST'])
def appsheet_sync_trigger():
    """Botón de Sincronizar Ahora"""
    try:
        if src.monitor and src.monitor.running:
            src.monitor.force_manual_sync()
            return jsonify({"success": True, "message": "Sync iniciada"}), 200
        else:
            return jsonify({"success": False, "message": "Monitor no activo o AppSheet deshabilitado"}), 503
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/appsheet/config', methods=['POST'])
def appsheet_config():
    return jsonify({"success": False, "message": "Configure via Variables de Entorno"}), 403
