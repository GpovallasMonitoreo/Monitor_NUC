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

bp = Blueprint('api', __name__, url_prefix='/api')

# Configuración de tiempos
TZ_CDMX = ZoneInfo("America/Mexico_City")
EMAIL_TIMEOUT_SECONDS = 45 

@bp.route('/report', methods=['POST'])
def report():
    """
    Endpoint que recibe los datos de los agentes (NUCs).
    """
    try:
        data = request.get_json()
        if not data or 'pc_name' not in data:
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        # Inyectar timestamp del servidor (CDMX)
        now = datetime.now(TZ_CDMX)
        data['timestamp'] = now.isoformat()
        
        # 1. Guardar en Storage Local (Tu lógica original de correos y JSON)
        if hasattr(src, 'storage') and src.storage:
            src.storage.save_device_report(data)
        
        # 2. Alimentar al Monitor de AppSheet (NUEVO) 

[Image of data ingestion flow]

        # Esto permite detectar cambios bruscos al instante y actualizar memoria
        if hasattr(src, 'monitor') and src.monitor:
            # Enviamos una copia para evitar conflictos de modificación
            src.monitor.ingest_data(data.copy())
        
        return jsonify({"status": "OK"})

    except Exception as e:
        print(f"Error en /report: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/data', methods=['GET'])
def get_data():
    """
    Endpoint consumido por el Dashboard.
    Aquí calculamos quién está OFFLINE y disparamos alertas rojas de CORREO.
    """
    try:
        if not hasattr(src, 'storage') or not src.storage:
            return jsonify({})

        raw_data = src.storage.get_all_devices()
        processed_data = {}
        now = datetime.now(TZ_CDMX)

        for pc_name, info in raw_data.items():
            # Crear copia para no modificar la DB original
            device_info = info.copy()
            
            # Calcular tiempo desde último reporte
            last_seen_str = info.get('timestamp')
            is_offline = True # Asumimos offline por defecto

            if last_seen_str:
                try:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    delta = (now - last_seen).total_seconds()
                    
                    # Si el tiempo es menor al límite, está ONLINE
                    if delta < EMAIL_TIMEOUT_SECONDS:
                        is_offline = False
                except ValueError:
                    pass # Error de fecha, se queda como offline
            
            # LÓGICA DE ALERTA ROJA (OFFLINE - CORREO)
            if is_offline:
                device_info['status'] = 'offline'
                
                # Verificamos si ya alertamos para no hacer spam
                alert_state = src.storage.alert_states.get(pc_name, {})
                if not alert_state.get('email_sent', False):
                    print(f"🔥 DESCONEXIÓN DETECTADA: {pc_name}")
                    if hasattr(src, 'alerts') and src.alerts:
                        src.alerts.send_offline_alert(pc_name, info)
                    
                    # Marcar como alertado
                    src.storage.alert_states[pc_name] = {'status': 'offline', 'email_sent': True}
            else:
                device_info['status'] = 'online'

            processed_data[pc_name] = device_info

        return jsonify(processed_data)

    except Exception as e:
        print(f"Error en /data: {e}")
        return jsonify({"error": str(e)}), 500

# --- NUEVO ENDPOINT: Sincronización Manual ---
@bp.route('/sync/manual', methods=['POST'])
def manual_sync():
    """
    Endpoint para forzar la sincronización con AppSheet desde un botón.
    """
    try:
        if hasattr(src, 'monitor') and src.monitor:
            # Ejecuta la sincronización en el hilo del monitor
            src.monitor.force_manual_sync()
            return jsonify({"status": "OK", "message": "Sincronización iniciada"}), 200
        else:
            return jsonify({"status": "error", "message": "Monitor no activo"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500
