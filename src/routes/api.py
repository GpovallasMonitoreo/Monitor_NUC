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
    # Tu lógica de offline/online se mantiene igual aquí...
    return jsonify(raw)

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

# --- RUTAS BITÁCORA (CRÍTICAS PARA QUE FUNCIONE EL GUARDADO) ---
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
        # Verificar que venga el device_name
        if 'device_name' not in data:
            return jsonify({"status": "error", "message": "Falta device_name"}), 400
            
        if src.appsheet and src.appsheet.add_history_entry(data):
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "Fallo al guardar"}), 500
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500
