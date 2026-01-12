import sys
import os
from flask import Blueprint, request, jsonify
from datetime import datetime
import json
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
    """Endpoint para recibir reportes de dispositivos"""
    try:
        data = request.get_json()
        if not data or 'pc_name' not in data: 
            return jsonify({
                "status": "error", 
                "message": "Falta pc_name en el reporte"
            }), 400
        
        data['timestamp'] = datetime.now(TZ_MX).isoformat()
        
        # Guardar en almacenamiento local
        if src.storage: 
            src.storage.save_device_report(data)
        
        # Enviar a AppSheet si está habilitado
        if src.monitor and src.appsheet and src.appsheet.enabled: 
            src.monitor.ingest_data(data.copy())
        
        return jsonify({"status": "OK", "message": "Reporte recibido"})
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Error interno: {str(e)}"
        }), 500

@bp.route('/data', methods=['GET'])
def get_data():
    """Obtiene datos de todos los dispositivos"""
    if not src.storage: 
        return jsonify({})
    
    raw = src.storage.get_all_devices()
    processed_data = {}
    now = datetime.now(TZ_MX)
    
    for pc_name, info in raw.items():
        device_info = info.copy()
        
        # Lógica de estado online/offline
        last = info.get('timestamp')
        if last:
            try:
                last_time = datetime.fromisoformat(last.replace('Z', '+00:00'))
                time_diff = (now - last_time).total_seconds()
                
                if time_diff > EMAIL_TIMEOUT_SECONDS:
                    device_info['status'] = 'offline'
                else:
                    device_info['status'] = 'online'
                    
            except Exception as e:
                device_info['status'] = 'unknown'
                device_info['error'] = str(e)
        
        processed_data[pc_name] = device_info
    
    return jsonify(processed_data)

# --- RUTAS APPSHEET ---
@bp.route('/appsheet/status', methods=['GET'])
def appsheet_status():
    """Obtiene el estado de conexión con AppSheet"""
    if not src.appsheet: 
        return jsonify({
            "status": "disabled", 
            "message": "AppSheet no inicializado"
        }), 200
    
    return jsonify(src.appsheet.get_status_info())

@bp.route('/appsheet/stats', methods=['GET'])
def appsheet_stats():
    """Obtiene estadísticas de AppSheet"""
    if src.appsheet: 
        return jsonify(src.appsheet.get_system_stats())
    return jsonify({})

@bp.route('/appsheet/sync', methods=['POST'])
def appsheet_sync_trigger():
    """Fuerza sincronización manual con AppSheet"""
    if src.monitor:
        src.monitor.force_manual_sync()
        return jsonify({
            "status": "success", 
            "message": "Sincronización manual iniciada"
        })
    
    return jsonify({
        "status": "error", 
        "message": "Monitor no disponible"
    }), 500

@bp.route('/appsheet/diagnose', methods=['GET'])
def appsheet_diagnose():
    """Endpoint para diagnóstico de AppSheet"""
    if not src.appsheet:
        return jsonify({
            "status": "error", 
            "message": "AppSheet no inicializado"
        }), 500
    
    try:
        # Probar conexión básica
        basic_test = src.appsheet._test_table_connection('devices')
        history_test = src.appsheet.test_history_connection()
        
        # Obtener información de configuración
        config_info = {
            "enabled": src.appsheet.enabled,
            "app_id": src.appsheet.app_id[:10] + "..." if src.appsheet.app_id else "None",
            "base_url": src.appsheet.base_url,
            "has_api_key": bool(src.appsheet.api_key) and "tu_api_key" not in src.appsheet.api_key
        }
        
        return jsonify({
            "status": "success",
            "diagnosis": {
                "tables": {
                    "devices": "connected" if basic_test else "disconnected",
                    "device_history": "connected" if history_test else "disconnected"
                },
                "config": config_info,
                "environment": {
                    "APPSHEET_ENABLED": os.getenv('APPSHEET_ENABLED', 'Not set'),
                    "APPSHEET_APP_ID_set": bool(os.getenv('APPSHEET_APP_ID'))
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

# --- RUTAS BITÁCORA ---
@bp.route('/history/all', methods=['GET'])
def get_history():
    """Obtiene todo el historial de bitácora"""
    try:
        if src.appsheet: 
            history = src.appsheet.get_full_history()
            return jsonify(history)
        
        return jsonify([])
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e),
            "data": []
        }), 500

@bp.route('/history/add', methods=['POST'])
def add_history():
    """Agrega una nueva entrada a la bitácora"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error", 
                "message": "No se recibieron datos"
            }), 400
        
        # Validación flexible para aceptar device_name o pc_name
        if 'device_name' not in data and 'pc_name' not in data:
            return jsonify({
                "status": "error", 
                "message": "Falta nombre del dispositivo (device_name o pc_name)"
            }), 400
        
        # Log para debug
        print(f"📨 Recibiendo ficha: {json.dumps(data, indent=2)}")
        
        if src.appsheet and src.appsheet.add_history_entry(data):
            return jsonify({
                "status": "success", 
                "message": "Ficha guardada exitosamente"
            })
        
        return jsonify({
            "status": "error", 
            "message": "No se pudo guardar en AppSheet. Verifica la conexión."
        }), 500
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Error interno: {str(e)}"
        }), 500

@bp.route('/history/test', methods=['POST'])
def test_history():
    """Endpoint de prueba para bitácora"""
    try:
        test_data = {
            "device_name": "MX_TEST_" + datetime.now().strftime("%H%M%S"),
            "unit": "ECOVALLAS",
            "action": "Prueba de sistema",
            "component": "Software",
            "description": "Prueba automática desde API",
            "req": "Sistema Automático",
            "exec": "API Test",
            "solved": True,
            "locName": "Oficina de Pruebas",
            "timestamp": datetime.now(TZ_MX).isoformat()
        }
        
        if src.appsheet and src.appsheet.add_history_entry(test_data):
            return jsonify({
                "status": "success", 
                "message": "Prueba exitosa",
                "test_data": test_data
            })
        
        return jsonify({
            "status": "error", 
            "message": "Prueba fallida"
        }), 500
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500
