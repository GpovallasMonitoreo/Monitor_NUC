import sys
import os
from flask import Blueprint, request, jsonify
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# Configuración de rutas para imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

# Importamos 'src' completo para acceder a las variables inyectadas (storage, alerts, monitor)
import src 

# --- ¡IMPORTANTE! ESTA LÍNEA DEBE IR ANTES DE LAS RUTAS ---
bp = Blueprint('api', __name__, url_prefix='/api')
# ----------------------------------------------------------

# Configuración de tiempos
TZ_CDMX = ZoneInfo("America/Mexico_City")
EMAIL_TIMEOUT_SECONDS = 45 

# ==========================================
# RUTAS DE INGESTA Y DATOS (NUCs y Dashboard)
# ==========================================

@bp.route('/report', methods=['POST'])
def report():
    """Endpoint que recibe los datos de los agentes (NUCs)."""
    try:
        data = request.get_json()
        if not data or 'pc_name' not in data:
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        # Inyectar timestamp
        now = datetime.now(TZ_CDMX)
        data['timestamp'] = now.isoformat()
        
        # 1. Guardar en Storage Local (Dashboard)
        if hasattr(src, 'storage') and src.storage:
            src.storage.save_device_report(data)
        
        # 2. Alimentar al Monitor de AppSheet (Watchdog + Picos)
        if hasattr(src, 'monitor') and src.monitor:
            src.monitor.ingest_data(data.copy())
        
        return jsonify({"status": "OK"})

    except Exception as e:
        print(f"Error en /report: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/data', methods=['GET'])
def get_data():
    """Endpoint consumido por el Dashboard para mostrar estados y alertas de correo."""
    try:
        if not hasattr(src, 'storage') or not src.storage:
            return jsonify({})

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
                except ValueError:
                    pass 
            
            # Lógica de Alerta Roja (Correo)
            if is_offline:
                device_info['status'] = 'offline'
                alert_state = src.storage.alert_states.get(pc_name, {})
                if not alert_state.get('email_sent', False):
                    if hasattr(src, 'alerts') and src.alerts:
                        src.alerts.send_offline_alert(pc_name, info)
                    src.storage.alert_states[pc_name] = {'status': 'offline', 'email_sent': True}
            else:
                device_info['status'] = 'online'

            processed_data[pc_name] = device_info

        return jsonify(processed_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/sync/manual', methods=['POST'])
def manual_sync():
    """Endpoint para forzar sincronización (Backend puro)"""
    try:
        if hasattr(src, 'monitor') and src.monitor:
            src.monitor.force_manual_sync()
            return jsonify({"status": "OK", "message": "Sincronización iniciada"}), 200
        return jsonify({"status": "error", "message": "Monitor inactivo"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# NUEVAS RUTAS PARA EL PANEL DE CONTROL APPSHEET
# ==========================================

@bp.route('/appsheet/status', methods=['GET'])
def appsheet_status():
    """
    Ruta que consume el Dashboard para ver si AppSheet está conectado.
    Resuelve el error 404 y SyntaxError.
    """
    try:
        if hasattr(src, 'appsheet') and src.appsheet:
            status_info = src.appsheet.get_status_info()
            
            if hasattr(src, 'monitor') and src.monitor:
                status_info['monitor_running'] = src.monitor.running
            else:
                status_info['monitor_running'] = False
                
            return jsonify(status_info), 200
        else:
            return jsonify({
                "status": "disabled",
                "message": "Servicio no inicializado",
                "available": False
            }), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/appsheet/sync', methods=['POST'])
def appsheet_sync_trigger():
    """Ruta para el botón 'Sincronizar Ahora' del frontend."""
    try:
        if hasattr(src, 'monitor') and src.monitor:
            src.monitor.force_manual_sync()
            return jsonify({
                "success": True, 
                "message": "Sincronización forzada iniciada"
            }), 200
        else:
            return jsonify({
                "success": False, 
                "message": "Monitor no activo"
            }), 503
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/appsheet/config', methods=['POST'])
def appsheet_config():
    """Placeholder de seguridad."""
    return jsonify({
        "success": False,
        "message": "Configure APPSHEET_API_KEY en variables de entorno."
    }), 403
