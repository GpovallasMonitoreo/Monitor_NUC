import os
import sys
import logging
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
from datetime import datetime

# Configurar Logging básico
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 1. RUTAS ABSOLUTAS
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

template_dir = os.path.join(base_dir, 'src', 'templates')
static_dir = os.path.join(base_dir, 'src', 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# 2. CONFIGURACIÓN
app.secret_key = os.environ.get('SECRET_KEY', 'argos_dev_key')
CORS(app)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 3. INICIALIZACIÓN DE SERVICIOS
# Importamos el contenedor global 'src'
import src

# Importamos las clases de los servicios
from src.services.storage_service import StorageService
from src.services.alert_service import AlertService

# IMPORTACIÓN CORREGIDA PARA APPSHEET SERVICE
try:
    from src.services.appsheet_service import AppSheetService
    logger.info("✅ AppSheetService importado desde src.services.appsheet_service")
except ImportError as e:
    logger.error(f"❌ Error importando AppSheetService: {e}")
    # Intentar importación alternativa
    try:
        sys.path.append(os.path.join(base_dir, 'src', 'services'))
        from appsheet_service import AppSheetService
        logger.info("✅ AppSheetService importado directamente desde services/appsheet_service")
    except ImportError as e2:
        logger.error(f"❌ Error importación alternativa: {e2}")
        # Crear un stub si no se puede importar
        class AppSheetServiceStub:
            def __init__(self):
                self.enabled = False
                self.api_key = ''
                self.app_id = ''
                self.base_url = ''
                self.last_sync_time = None
                self.table_status = {}
                
            def _test_table_connection(self, table_name):
                return False
                
            def test_history_connection(self):
                return False
                
            def get_status_info(self):
                return {"status": "disabled", "available": False}
                
            def add_history_entry(self, log_data):
                logger.warning("AppSheetService no disponible - usando stub")
                return False
                
            def get_full_history(self):
                return []
                
            def get_system_stats(self):
                return {'avg_latency': 0, 'total_devices': 0}
            
            def get_or_create_device(self, device_data):
                return False, None, False
            
            def add_latency_to_history(self, data):
                return False
            
            def add_alert(self, data, type_alert, msg, sev):
                return False
            
            def _make_safe_request(self, table, action, properties=None):
                return None
        
        AppSheetService = AppSheetServiceStub
        logger.warning("⚠️  Usando AppSheetService stub - funcionalidad limitada")

from src.services.monitor_service import DeviceMonitorManager

# Definir ruta de la DB
data_dir = os.path.join(base_dir, 'data')
os.makedirs(data_dir, exist_ok=True)
db_path = os.path.join(data_dir, 'inventory_db.json')

logger.info("⚙️ Inicializando servicios centrales...")

# --- INYECCIÓN DE DEPENDENCIAS EN SRC ---
# 1. Alertas
src.alerts = AlertService(app)

# 2. Storage (Base de datos local)
src.storage = StorageService(db_path, alert_service=src.alerts)

# 3. AppSheet (Nube) - CON MANEJO DE ERRORES
try:
    src.appsheet = AppSheetService()
    appsheet_status = src.appsheet.get_status_info()
    logger.info(f"✅ AppSheet inicializado. Estado: {'HABILITADO' if src.appsheet.enabled else 'DESHABILITADO'}")
    logger.info(f"📊 Estado AppSheet: {appsheet_status}")
    
    if src.appsheet.enabled:
        # Mostrar estado de cada tabla
        if hasattr(src.appsheet, 'table_status') and src.appsheet.table_status:
            logger.info("📡 Estado de tablas AppSheet:")
            for table, connected in src.appsheet.table_status.items():
                status = "✅" if connected else "❌"
                logger.info(f"   {status} {table}: {'Conectada' if connected else 'No conectada'}")
        else:
            # Probar conexión con método legacy
            connection_ok = src.appsheet._test_table_connection('devices') if hasattr(src.appsheet, '_test_table_connection') else False
            history_ok = src.appsheet.test_history_connection() if hasattr(src.appsheet, 'test_history_connection') else False
            logger.info(f"📡 Conexión AppSheet - Devices: {'✅' if connection_ok else '❌'}, History: {'✅' if history_ok else '❌'}")
            
except Exception as e:
    logger.error(f"❌ Error inicializando AppSheetService: {e}")
    import traceback
    logger.error(traceback.format_exc())
    
    # Crear un stub si falla
    class AppSheetStub:
        def __init__(self):
            self.enabled = False
            self.api_key = ''
            self.app_id = ''
            self.base_url = ''
            self.last_sync_time = None
            self.table_status = {}
            
        def _test_table_connection(self, table_name):
            return False
            
        def test_history_connection(self):
            return False
            
        def get_status_info(self):
            return {"status": "error", "available": False, "error": "Initialization failed"}
            
        def add_history_entry(self, log_data):
            logger.warning("AppSheet no disponible - no se guardarán fichas")
            return False
            
        def get_full_history(self):
            return []
            
        def get_system_stats(self):
            return {'avg_latency': 0, 'total_devices': 0, 'status': 'error'}
        
        def get_or_create_device(self, device_data):
            return False, None, False
        
        def add_latency_to_history(self, data):
            return False
        
        def add_alert(self, data, type_alert, msg, sev):
            return False
        
        def _make_safe_request(self, table, action, properties=None):
            return None
    
    src.appsheet = AppSheetStub()

# 4. Monitor (Hilo de fondo)
try:
    if src.appsheet and src.appsheet.enabled:
        src.monitor = DeviceMonitorManager(src.appsheet)
        src.monitor.start() # Iniciar el hilo
        logger.info("✅ Monitor de dispositivos iniciado")
    else:
        src.monitor = None
        logger.info("⚠️ Monitor no iniciado porque AppSheet está deshabilitado")
except Exception as e:
    logger.error(f"❌ Error iniciando monitor: {e}")
    src.monitor = None

logger.info(f"✅ ARGOS: Storage inicializado en {db_path}")

# 4. BLUEPRINTS
# Registramos las rutas DESPUÉS de haber inicializado los servicios
try:
    from src.routes.api import bp as api_bp
    app.register_blueprint(api_bp)
    logger.info("✅ Blueprint API registrado")
except ImportError as e:
    logger.error(f"❌ Error importando blueprint API: {e}")
    # Crear rutas básicas si el blueprint falla
    @app.route('/api/data')
    def api_data_fallback():
        return jsonify({"status": "error", "message": "API blueprint no disponible"})
    
    @app.route('/api/history/add', methods=['POST'])
    def api_history_add_fallback():
        return jsonify({"status": "error", "message": "API blueprint no disponible"}), 500

try:
    from src.routes.views import bp as views_bp
    app.register_blueprint(views_bp)
    logger.info("✅ Blueprint Views registrado")
except ImportError as e:
    logger.error(f"❌ Error importando blueprint Views: {e}")
    # Crear rutas básicas si el blueprint falla
    @app.route('/')
    def home_fallback():
        return "Argos System - Views blueprint no disponible"

# ==================== NUEVAS RUTAS PARA APPSHEET ====================

@app.route('/api/appsheet/status', methods=['GET'])
def appsheet_status():
    """Endpoint para verificar estado de AppSheet"""
    try:
        if src.appsheet and hasattr(src.appsheet, 'get_status_info'):
            status = src.appsheet.get_status_info()
            return jsonify({
                "success": True,
                "available": status.get('enabled', False),
                "connected": status.get('connection_status') == 'connected',
                "timestamp": datetime.now().isoformat(),
                "status": status
            })
        else:
            return jsonify({
                "success": False,
                "available": False,
                "connected": False,
                "error": "AppSheet service not available",
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "available": False,
            "connected": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/appsheet/stats', methods=['GET'])
def get_appsheet_stats():
    """Obtiene estadísticas de AppSheet para el dashboard"""
    try:
        if not src.appsheet or not src.appsheet.enabled:
            return jsonify({
                "success": False,
                "error": "AppSheet service not enabled",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Obtener historial reciente para calcular stats
        history = src.appsheet.get_full_history(limit=100)
        
        # Contar dispositivos únicos
        unique_devices = set()
        if history:
            for entry in history:
                if isinstance(entry, dict):
                    device_id = entry.get('device_id')
                    if device_id:
                        unique_devices.add(device_id)
        
        # Calcular tiempo desde última sincronización
        last_sync = None
        if hasattr(src.appsheet, 'last_sync_time') and src.appsheet.last_sync_time:
            last_sync = src.appsheet.last_sync_time.isoformat()
        
        # Obtener información de tablas
        tables_connected = 0
        if hasattr(src.appsheet, 'table_status'):
            tables_connected = sum(1 for v in src.appsheet.table_status.values() if v)
        
        stats = {
            "total_records": len(history),
            "total_devices": len(unique_devices),
            "active_alerts": 0,  # Podrías calcular esto si tienes alertas
            "last_sync": last_sync,
            "uptime_percent": 99.9,  # Placeholder
            "avg_latency": 45,  # Placeholder
            "tables_connected": tables_connected
        }
        
        return jsonify({
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "stats": stats
        })
        
    except Exception as e:
        logger.error(f"Error en get_appsheet_stats: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/appsheet/sync', methods=['POST'])
def manual_sync_to_appsheet():
    """Sincronización manual de datos a AppSheet"""
    try:
        if not src.appsheet or not src.appsheet.enabled:
            return jsonify({
                "success": False,
                "error": "AppSheet service not enabled",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Obtener datos locales
        local_data = {}
        if src.storage and hasattr(src.storage, 'get_all_devices'):
            local_data = src.storage.get_all_devices()
        
        results = {
            "synced_devices": 0,
            "synced_records": 0,
            "errors": 0,
            "details": []
        }
        
        # Sincronizar cada dispositivo
        for device_id, device_data in local_data.items():
            try:
                if device_data and isinstance(device_data, dict):
                    # Sincronizar dispositivo
                    success, _, _ = src.appsheet.get_or_create_device(device_data)
                    if success:
                        results["synced_devices"] += 1
                        
                        # Crear entrada de historial
                        history_entry = {
                            "pc_name": device_data.get('pc_name', device_id),
                            "action": "manual_sync",
                            "desc": f"Sincronización manual desde dashboard",
                            "exec": "Dashboard",
                            "unit": device_data.get('unit', 'General'),
                            "solved": "true",
                            "locName": device_data.get('locName', device_data.get('pc_name', 'Unknown')),
                            "status_snapshot": "synced"
                        }
                        
                        history_success = src.appsheet.add_history_entry(history_entry)
                        if history_success:
                            results["synced_records"] += 1
                        
                        results["details"].append({
                            "device": device_id,
                            "device_sync": success,
                            "history_sync": history_success
                        })
                    else:
                        results["errors"] += 1
            except Exception as e:
                results["errors"] += 1
                results["details"].append({
                    "device": device_id,
                    "error": str(e)
                })
        
        return jsonify({
            "success": True,
            "status": "success" if results["errors"] == 0 else "partial",
            "message": f"Sincronizados {results['synced_devices']} dispositivos con {results['synced_records']} registros",
            "results": results,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en manual_sync_to_appsheet: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/appsheet/test-all', methods=['POST', 'GET'])
def test_appsheet_all():
    """Prueba completa de AppSheet con tus tablas"""
    try:
        if not src.appsheet or not src.appsheet.enabled:
            return jsonify({
                "success": False,
                "error": "AppSheet service not enabled",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "service_status": src.appsheet.get_status_info(),
            "tests": {}
        }
        
        # Test 1: Crear dispositivo de prueba
        test_device = {
            "pc_name": f"TEST_{datetime.now().strftime('%H%M%S')}",
            "unit": "Testing",
            "public_ip": "192.168.1.100",
            "locName": "Oficina Test"
        }
        
        success, device_id, created = src.appsheet.get_or_create_device(test_device)
        results["tests"]["create_device"] = {
            "success": success,
            "device_id": device_id,
            "created": created,
            "data": test_device
        }
        
        # Test 2: Añadir historial
        if success and device_id:
            history_data = {
                "pc_name": test_device["pc_name"],
                "action": "system_test",
                "desc": "Prueba automática de conexión AppSheet",
                "exec": "Sistema",
                "unit": "Testing",
                "solved": "true",
                "locName": "Oficina Test",
                "status_snapshot": "testing"
            }
            
            history_success = src.appsheet.add_history_entry(history_data)
            results["tests"]["add_history"] = {
                "success": history_success,
                "data": history_data
            }
        
        # Test 3: Añadir latencia
        latency_data = {
            "pc_name": test_device["pc_name"],
            "latency": 45,
            "cpu_load_percent": 25,
            "ram_percent": 60,
            "temperature_c": 35,
            "disk_percent": 40,
            "status": "online",
            "extended_sensors": "CPU:25,RAM:60,TEMP:35"
        }
        
        latency_success = src.appsheet.add_latency_to_history(latency_data)
        results["tests"]["add_latency"] = {
            "success": latency_success,
            "data": latency_data
        }
        
        # Test 4: Añadir alerta
        alert_success = src.appsheet.add_alert(
            {"pc_name": test_device["pc_name"]},
            "connection_test",
            "Prueba automática de alertas en AppSheet",
            "info"
        )
        results["tests"]["add_alert"] = {
            "success": alert_success,
            "type": "connection_test",
            "severity": "info"
        }
        
        # Test 5: Leer historial
        history = src.appsheet.get_full_history(limit=5)
        results["tests"]["read_history"] = {
            "success": len(history) > 0,
            "count": len(history),
            "sample": history[0] if history else None
        }
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error en test_appsheet_all: {e}")
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().isoformat()
        }), 500

# ==================== RUTAS EXISTENTES (mantenidas) ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session: return redirect(url_for('views.home'))
    if request.method == 'POST':
        if request.form.get('username') == 'gpovallas' and request.form.get('password') == 'admin':
            session['username'] = 'gpovallas'
            return redirect(url_for('views.home'))
        return render_template('login.html', error="Credenciales inválidas")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/health')
def health():
    try:
        monitor_status = "RUNNING" if (src.monitor and hasattr(src.monitor, 'running') and src.monitor.running) else "STOPPED"
        appsheet_enabled = src.appsheet.enabled if (src.appsheet and hasattr(src.appsheet, 'enabled')) else False
        appsheet_status = src.appsheet.get_status_info() if (src.appsheet and hasattr(src.appsheet, 'get_status_info')) else {"status": "unknown"}
        
        return jsonify({
            "status": "Argos Online",
            "monitor": monitor_status,
            "appsheet_enabled": appsheet_enabled,
            "appsheet_status": appsheet_status,
            "services": {
                "storage": "OK" if src.storage else "ERROR",
                "alerts": "OK" if src.alerts else "ERROR",
                "appsheet": "OK" if src.appsheet else "ERROR",
                "monitor": "OK" if src.monitor else "ERROR"
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "Argos Error",
            "error": str(e),
            "services": {
                "storage": "OK" if src.storage else "ERROR",
                "alerts": "OK" if src.alerts else "ERROR",
                "appsheet": "ERROR",
                "monitor": "ERROR"
            },
            "timestamp": datetime.now().isoformat()
        }), 500

# 6. MANEJO DE ERRORES GLOBALES
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        "status": "error", 
        "message": "Ruta no encontrada",
        "timestamp": datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"❌ Error interno del servidor: {error}")
    return jsonify({
        "status": "error", 
        "message": "Error interno del servidor",
        "timestamp": datetime.now().isoformat()
    }), 500

# 7. MIDDLEWARE PARA HEADERS DE SEGURIDAD
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# 8. ARRANQUE
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"🚀 Iniciando Argos en puerto {port} (debug: {debug_mode})")
    logger.info(f"📁 Base dir: {base_dir}")
    logger.info(f"📁 Template dir: {template_dir}")
    logger.info(f"📁 Static dir: {static_dir}")
    
    # Verificar estructura de directorios
    if not os.path.exists(template_dir):
        logger.warning(f"⚠️  Directorio de templates no encontrado: {template_dir}")
        os.makedirs(template_dir, exist_ok=True)
    
    if not os.path.exists(static_dir):
        logger.warning(f"⚠️  Directorio static no encontrado: {static_dir}")
        os.makedirs(static_dir, exist_ok=True)
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
