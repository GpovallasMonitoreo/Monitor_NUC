import sys
import os
from flask import Blueprint, request, jsonify
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# Configuración imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

import src 

bp = Blueprint('api', __name__, url_prefix='/api')

TZ_CDMX = ZoneInfo("America/Mexico_City")
EMAIL_TIMEOUT_SECONDS = 45 

@bp.route('/report', methods=['POST'])
def report():
    try:
        data = request.get_json()
        if not data or 'pc_name' not in data:
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        now = datetime.now(TZ_CDMX)
        data['timestamp'] = now.isoformat()
        
        # 1. Storage Local (Dashboard)
        if hasattr(src, 'storage') and src.storage:
            src.storage.save_device_report(data)
        
        # 2. Monitor AppSheet (Watchdog + Picos)
        if hasattr(src, 'monitor') and src.monitor:
            src.monitor.ingest_data(data.copy())
        
        return jsonify({"status": "OK"})

    except Exception as e:
        print(f"Error en /report: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/data', methods=['GET'])
def get_data():
    try:
        if not hasattr(src, 'storage') or not src.storage: return jsonify({})

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
    try:
        if hasattr(src, 'monitor') and src.monitor:
            src.monitor.force_manual_sync()
            return jsonify({"status": "OK", "message": "Sync iniciada"}), 200
        return jsonify({"status": "error", "message": "Monitor inactivo"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500
