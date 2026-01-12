import sys
import os
from flask import Blueprint, request, jsonify
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import src 

bp = Blueprint('api', __name__, url_prefix='/api')
TZ_MX = ZoneInfo("America/Mexico_City")
EMAIL_TIMEOUT_SECONDS = 45 

# --- RUTAS CORE ---
@bp.route('/report', methods=['POST'])
def report():
    try:
        data = request.get_json()
        if not data or 'pc_name' not in data: return jsonify({"status": "error"}), 400
        data['timestamp'] = datetime.now(TZ_MX).isoformat()
        
        if src.storage: src.storage.save_device_report(data)
        if src.monitor and src.appsheet.enabled: src.monitor.ingest_data(data.copy())
        
        return jsonify({"status": "OK"})
    except: return jsonify({"status": "error"}), 500

@bp.route('/data', methods=['GET'])
def get_data():
    if not src.storage: return jsonify({})
    raw = src.storage.get_all_devices()
    processed_data = {}
    now = datetime.now(TZ_MX)
    for pc_name, info in raw.items():
        device_info = info.copy()
        last = info.get('timestamp')
        if last:
            try:
                if (now - datetime.fromisoformat(last)).total_seconds() > EMAIL_TIMEOUT_SECONDS:
                    device_info['status'] = 'offline'
                else:
                    device_info['status'] = 'online'
            except: pass
        processed_data[pc_name] = device_info
    return jsonify(processed_data)

# --- RUTAS APPSHEET ---
@bp.route('/appsheet/status', methods=['GET'])
def appsheet_status():
    if not src.appsheet: return jsonify({"status": "disabled"}), 200
    return jsonify(src.appsheet.get_status_info())

@bp.route('/appsheet/stats', methods=['GET'])
def appsheet_stats():
    if src.appsheet: return jsonify(src.appsheet.get_system_stats())
    return jsonify({})

@bp.route('/appsheet/sync', methods=['POST'])
def appsheet_sync_trigger():
    if src.monitor:
        src.monitor.force_manual_sync()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

# --- RUTAS BITÁCORA ---
@bp.route('/history/all', methods=['GET'])
def get_history():
    try:
        if src.appsheet: return jsonify(src.appsheet.get_full_history())
        return jsonify([])
    except: return jsonify([])

@bp.route('/history/add', methods=['POST'])
def add_history():
    try:
        data = request.get_json()
        # Aseguramos que tenemos al menos un nombre
        if 'device_name' not in data and 'pc_name' not in data:
            return jsonify({"status": "error", "message": "Falta nombre del dispositivo"}), 400
            
        if src.appsheet and src.appsheet.add_history_entry(data):
            return jsonify({"status": "success"})
        
        # Si falla en el servicio, devolvemos error 500 para que el frontend lo sepa
        return jsonify({"status": "error", "message": "Fallo al guardar en AppSheet (Verificar logs)"}), 500
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500
