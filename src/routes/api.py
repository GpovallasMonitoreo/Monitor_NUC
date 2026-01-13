import sys
import os
from flask import Blueprint, request, jsonify
from datetime import datetime
import json
import traceback

# Manejo de zonas horarias compatible con Python < 3.9
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import src 

bp = Blueprint('api', __name__, url_prefix='/api')
TZ_MX = ZoneInfo("America/Mexico_City")
EMAIL_TIMEOUT_SECONDS = 45 

# ==========================================================
# RUTAS DE REPORTES (Dispositivos -> Servidor)
# ==========================================================
@bp.route('/report', methods=['POST'])
def report():
    """Endpoint principal: Recibe heartbeat de los agentes en las NUCs"""
    try:
        data = request.get_json()
        if not data or 'pc_name' not in data: 
            print("❌ /report: Falta pc_name en el reporte")
            return jsonify({"status": "error", "message": "Falta pc_name"}), 400
        
        # Estampamos la hora del servidor
        data['timestamp'] = datetime.now(TZ_MX).isoformat()
        
        # 1. Guardar en DB Local (JSON)
        if src.storage: 
            src.storage.save_device_report(data)
        
        # 2. Pasar al Monitor (que decide si enviar a AppSheet)
        if src.monitor and src.appsheet and src.appsheet.enabled: 
            src.monitor.ingest_data(data.copy())
        
        return jsonify({"status": "OK", "message": "Reporte recibido"})
        
    except Exception as e:
        print(f"❌ Error en /report: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/data', methods=['GET'])
def get_data():
    """Endpoint para el Frontend: Devuelve estado de todos los equipos"""
    try:
        if not src.storage: return jsonify({})
        
        raw = src.storage.get_all_devices()
        processed_data = {}
        now = datetime.now(TZ_MX)
        
        for pc_name, info in raw.items():
            device_info = info.copy()
            # Cálculo de estado Online/Offline basado en tiempo
            last = info.get('timestamp')
            if last:
                try:
                    # Normalizamos fecha para comparación
                    last_time = datetime.fromisoformat(last.replace('Z', '+00:00'))
                    time_diff = (now - last_time).total_seconds()
                    device_info['status'] = 'offline' if time_diff > EMAIL_TIMEOUT_SECONDS else 'online'
                except:
                    device_info['status'] = 'unknown'
            
            processed_data[pc_name] = device_info
        
        return jsonify(processed_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================================
# RUTAS DE APPSHEET (Diagnóstico y Estado)
# ==========================================================
@bp.route('/appsheet/status', methods=['GET'])
def appsheet_status():
    """Estado de conexión para el dashboard"""
    try:
        if not src.appsheet: 
            return jsonify({"status": "disabled", "message": "No inicializado"}), 200
        return jsonify(src.appsheet.get_status_info())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/appsheet/stats', methods=['GET'])
def appsheet_stats():
    """Estadísticas de registros (Latency, Uptime)"""
    try:
        if src.appsheet: return jsonify(src.appsheet.get_system_stats())
        return jsonify({})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/appsheet/diagnose', methods=['GET'])
def appsheet_diagnose():
    """
    Diagnóstico profundo. 
    Intenta leer 1 fila de cada tabla para verificar permisos.
    """
    try:
        if not src.appsheet:
            return jsonify({"status": "error", "message": "AppSheet OFF"}), 500
        
        print("🔍 Ejecutando diagnóstico de tablas...")
        basic_test = False
        history_test = False
        
        # Usamos _make_safe_request que es el método robusto del servicio nuevo
        if hasattr(src.appsheet, '_make_safe_request'):
            # Prueba Devices
            res_dev = src.appsheet._make_safe_request("devices", "Find", properties={"Top": 1})
            basic_test = res_dev is not None
            
            # Prueba History
            res_hist = src.appsheet._make_safe_request("device_history", "Find", properties={"Top": 1})
            history_test = res_hist is not None
        
        return jsonify({
            "status": "success",
            "diagnosis": {
                "tables": {
                    "devices": "connected" if basic_test else "disconnected",
                    "device_history": "connected" if history_test else "disconnected"
                },
                "appsheet_enabled": src.appsheet.enabled
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================================
# RUTAS DE BITÁCORA (Historial)
# ==========================================================
@bp.route('/history/all', methods=['GET'])
def get_history():
    """Lectura de bitácora desde AppSheet"""
    try:
        if src.appsheet: 
            history = src.appsheet.get_full_history()
            return jsonify(history)
        return jsonify([])
    except Exception as e:
        print(f"❌ Error history/all: {e}")
        return jsonify([]), 500

@bp.route('/history/add', methods=['POST'])
def add_history():
    """
    Escritura en bitácora.
    Recibe datos del Frontend, los valida y los manda al Servicio.
    """
    try:
        data = request.get_json()
        if not data: return jsonify({"status": "error", "message": "Sin datos"}), 400
        
        print(f"📨 /history/add payload: {json.dumps(data, ensure_ascii=False)}")
        
        # Validación mínima
        if not data.get('device_name') or not data.get('action'):
            return jsonify({"status": "error", "message": "Faltan campos obligatorios"}), 400
        
        # Timestamp servidor
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now(TZ_MX).isoformat()
        
        # Enviar al servicio
        success = False
        if src.appsheet and src.appsheet.enabled:
            success = src.appsheet.add_history_entry(data)
        
        if success:
            return jsonify({"status": "success", "message": "Guardado en AppSheet"})
        else:
            # Si falla (o AppSheet devuelve error), avisamos al frontend
            return jsonify({"status": "error", "message": "No se pudo conectar con AppSheet"}), 500
            
    except Exception as e:
        print(f"❌ Excepción en /history/add: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
