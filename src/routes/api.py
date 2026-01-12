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
            print("❌ /report: Falta pc_name en el reporte")
            return jsonify({
                "status": "error", 
                "message": "Falta pc_name en el reporte"
            }), 400
        
        data['timestamp'] = datetime.now(TZ_MX).isoformat()
        
        print(f"📨 /report recibió datos de {data.get('pc_name')}")
        
        # Guardar en almacenamiento local
        if src.storage: 
            src.storage.save_device_report(data)
        
        # Enviar a AppSheet si está habilitado
        if src.monitor and src.appsheet and src.appsheet.enabled: 
            src.monitor.ingest_data(data.copy())
        
        return jsonify({"status": "OK", "message": "Reporte recibido"})
        
    except Exception as e:
        print(f"❌ Error en /report: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Error interno: {str(e)}"
        }), 500

@bp.route('/data', methods=['GET'])
def get_data():
    """Obtiene datos de todos los dispositivos"""
    try:
        if not src.storage: 
            print("⚠️  /data: Storage no disponible")
            return jsonify({})
        
        raw = src.storage.get_all_devices()
        processed_data = {}
        now = datetime.now(TZ_MX)
        
        print(f"📊 /data: Procesando {len(raw)} dispositivos")
        
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
        
        print(f"✅ /data: Devolviendo {len(processed_data)} dispositivos procesados")
        return jsonify(processed_data)
        
    except Exception as e:
        print(f"❌ Error en /data: {e}")
        return jsonify({"error": str(e)}), 500

# --- RUTAS APPSHEET ---
@bp.route('/appsheet/status', methods=['GET'])
def appsheet_status():
    """Obtiene el estado de conexión con AppSheet"""
    try:
        if not src.appsheet: 
            print("⚠️  /appsheet/status: AppSheet no inicializado")
            return jsonify({
                "status": "disabled", 
                "message": "AppSheet no inicializado"
            }), 200
        
        status_info = src.appsheet.get_status_info()
        print(f"📡 /appsheet/status: {status_info}")
        return jsonify(status_info)
        
    except Exception as e:
        print(f"❌ Error en /appsheet/status: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

@bp.route('/appsheet/stats', methods=['GET'])
def appsheet_stats():
    """Obtiene estadísticas de AppSheet"""
    try:
        if src.appsheet: 
            stats = src.appsheet.get_system_stats()
            print(f"📊 /appsheet/stats: {stats}")
            return jsonify(stats)
        
        print("⚠️  /appsheet/stats: AppSheet no disponible")
        return jsonify({})
        
    except Exception as e:
        print(f"❌ Error en /appsheet/stats: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

@bp.route('/appsheet/diagnose', methods=['GET'])
def appsheet_diagnose():
    """Endpoint para diagnóstico de AppSheet"""
    try:
        if not src.appsheet:
            print("❌ /appsheet/diagnose: AppSheet no inicializado")
            return jsonify({
                "status": "error", 
                "message": "AppSheet no inicializado"
            }), 500
        
        print("🔍 /appsheet/diagnose: Ejecutando diagnóstico...")
        
        # Probar conexión básica
        basic_test = False
        history_test = False
        
        if hasattr(src.appsheet, '_make_appsheet_request'):
            # Probar devices
            devices_result = src.appsheet._make_appsheet_request("devices", "Find", properties={"Top": 1})
            basic_test = devices_result is not None
            
            # Probar device_history
            history_result = src.appsheet._make_appsheet_request("device_history", "Find", properties={"Top": 1})
            history_test = history_result is not None
        
        print(f"📊 /appsheet/diagnose: devices={basic_test}, history={history_test}")
        
        return jsonify({
            "status": "success",
            "diagnosis": {
                "tables": {
                    "devices": "connected" if basic_test else "disconnected",
                    "device_history": "connected" if history_test else "disconnected"
                },
                "appsheet_enabled": src.appsheet.enabled if src.appsheet else False,
                "environment": {
                    "APPSHEET_ENABLED": os.getenv('APPSHEET_ENABLED', 'Not set'),
                    "APPSHEET_APP_ID_set": bool(os.getenv('APPSHEET_APP_ID'))
                }
            }
        })
        
    except Exception as e:
        print(f"❌ Error en /appsheet/diagnose: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

@bp.route('/appsheet/test-history', methods=['POST'])
def test_history_entry():
    """Endpoint para probar la inserción de una ficha de prueba"""
    try:
        if not src.appsheet:
            print("❌ /appsheet/test-history: AppSheet no inicializado")
            return jsonify({
                "status": "error", 
                "message": "AppSheet no inicializado"
            }), 500
        
        # Crear datos de prueba
        test_data = {
            "device_name": f"MX_TEST_{datetime.now().strftime('%H%M%S')}",
            "pc_name": f"MX_TEST_{datetime.now().strftime('%H%M%S')}",
            "unit": "ECOVALLAS",
            "action": "Prueba de Sistema",
            "what": "NUC",
            "desc": "Prueba automática de funcionalidad de bitácora",
            "req": "Sistema Automático",
            "exec": "API Test",
            "solved": True,
            "timestamp": datetime.now(TZ_MX).isoformat()
        }
        
        print(f"🧪 /appsheet/test-history: Enviando datos de prueba")
        print(json.dumps(test_data, indent=2, ensure_ascii=False))
        
        success = src.appsheet.add_history_entry(test_data)
        
        if success:
            print("✅ /appsheet/test-history: Prueba exitosa")
            return jsonify({
                "status": "success", 
                "message": "Prueba de inserción exitosa",
                "test_data": test_data
            })
        else:
            print("❌ /appsheet/test-history: Prueba fallida")
            return jsonify({
                "status": "error", 
                "message": "Prueba de inserción falló"
            }), 500
        
    except Exception as e:
        print(f"❌ Error en /appsheet/test-history: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Error en prueba: {str(e)}"
        }), 500

# --- RUTAS BITÁCORA ---
@bp.route('/history/all', methods=['GET'])
def get_history():
    """Obtiene todo el historial de bitácora"""
    try:
        print("📋 /history/all: Solicitando historial completo...")
        
        if src.appsheet: 
            history = src.appsheet.get_full_history()
            print(f"✅ /history/all: Devolviendo {len(history)} registros")
            
            if history and len(history) > 0:
                print(f"📊 Muestra primer registro:")
                print(f"   device_id: {history[0].get('device_id')}")
                print(f"   acción: {history[0].get('action_type')}")
                print(f"   componente: {history[0].get('component')}")
                print(f"   fecha: {history[0].get('timestamp')}")
            
            return jsonify(history)
        
        print("⚠️  /history/all: AppSheet no disponible")
        return jsonify([])
        
    except Exception as e:
        print(f"❌ Error en /history/all: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e),
            "data": []
        }), 500

@bp.route('/history/device/<device_name>', methods=['GET'])
def get_device_history(device_name):
    """Obtiene historial específico para un dispositivo"""
    try:
        decoded_device_name = device_name
        print(f"📋 /history/device/{decoded_device_name}: Solicitando historial específico...")
        
        if src.appsheet: 
            history = src.appsheet.get_history_for_device(decoded_device_name)
            print(f"✅ /history/device/{decoded_device_name}: Encontrados {len(history)} registros")
            
            if history and len(history) > 0:
                print(f"📊 Muestra primer registro para {decoded_device_name}:")
                print(f"   device_id: {history[0].get('device_id')}")
                print(f"   acción: {history[0].get('action_type')}")
                print(f"   fecha: {history[0].get('timestamp')}")
            
            return jsonify(history)
        
        print(f"⚠️  /history/device/{decoded_device_name}: AppSheet no disponible")
        return jsonify([])
        
    except Exception as e:
        print(f"❌ Error en /history/device/{device_name}: {e}")
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
            print("❌ /history/add: No se recibieron datos")
            return jsonify({
                "status": "error", 
                "message": "No se recibieron datos"
            }), 400
        
        print(f"📨 /history/add recibió datos:")
        print(json.dumps(data, indent=2, ensure_ascii=False
