import os
import sys
import logging
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS

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
    # Intentar importar desde la ruta correcta
    from src.services.appsheet_service import AppSheetService
    logger.info("✅ AppSheetService importado desde src.services.appsheet_service")
except ImportError as e:
    logger.error(f"❌ Error importando AppSheetService: {e}")
    # Intentar importación alternativa
    try:
        # Intentar importar directamente
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
    logger.info(f"✅ AppSheet inicializado. Estado: {'HABILITADO' if src.appsheet.enabled else 'DESHABILITADO'}")
    if src.appsheet.enabled:
        # Probar conexión inicial
        connection_ok = src.appsheet._test_table_connection('devices') if hasattr(src.appsheet, '_test_table_connection') else False
        history_ok = src.appsheet.test_history_connection() if hasattr(src.appsheet, 'test_history_connection') else False
        logger.info(f"📡 Conexión AppSheet - Devices: {'✅' if connection_ok else '❌'}, History: {'✅' if history_ok else '❌'}")
except Exception as e:
    logger.error(f"❌ Error inicializando AppSheetService: {e}")
    # Crear un stub si falla
    class AppSheetStub:
        def __init__(self):
            self.enabled = False
            self.api_key = ''
            self.app_id = ''
            self.base_url = ''
            self.last_sync_time = None
            
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

# 5. RUTAS DE SISTEMA (Login/Health)
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
            }
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
            }
        }), 500

# 6. MANEJO DE ERRORES GLOBALES
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"status": "error", "message": "Ruta no encontrada"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"❌ Error interno del servidor: {error}")
    return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

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
