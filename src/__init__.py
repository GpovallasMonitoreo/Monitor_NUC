import os
import logging
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# Configurar Logging básico
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno (.env)
load_dotenv()

# ==========================================
# 1. INSTANCIAS GLOBALES (SINGLETONS)
# ==========================================
storage = None   # Configuración local (JSON)
alerts = None    # Sistema de alertas
supabase = None  # Base de datos Nube
monitor = None   # Hilo de monitoreo

def create_app():
    """
    Fábrica de Aplicación: Crea y configura la instancia de Flask.
    """
    app = Flask(__name__)
    
    # Configuración básica
    app.secret_key = os.environ.get('SECRET_KEY', 'argos_dev_key_secure')
    CORS(app)

    # Rutas base
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, '..', 'data', 'inventory_config.json')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # ==========================================
    # 2. INICIALIZACIÓN DE SERVICIOS
    # ==========================================
    global storage, alerts, supabase, monitor

    logger.info("⚙️ Inicializando servicios de Argos (Supabase Edition)...")

    # A. Servicios Base
    try:
        from src.services.alert_service import AlertService
        from src.services.storage_service import StorageService
        
        alerts = AlertService(app)
        storage = StorageService(db_path, alert_service=alerts)
        logger.info("✅ Servicios Locales (Alerts/Storage) iniciados")
    except Exception as e:
        logger.error(f"❌ Error crítico en servicios locales: {e}")

    # B. Supabase Service
    from src.services.supabase_service import SupabaseService
    
    # Definimos una bandera para saber si es el servicio real
    is_real_supabase = False

    try:
        supabase = SupabaseService()
        is_real_supabase = True
        logger.info("✅ Supabase Service conectado correctamente")
    except Exception as e:
        logger.error(f"❌ Fallo al conectar con Supabase: {e}")
        logger.warning("⚠️ El sistema funcionará solo en modo local")
        
        # Stub simple inline (definido aquí por si falla)
        class SupabaseStub:
            def buffer_metric(self, *args, **kwargs): pass
            def get_device_history(self, *args, **kwargs): return []
            def run_nightly_cleanup(self): pass
            def upsert_device_status(self, *args, **kwargs): pass
        
        supabase = SupabaseStub()
        is_real_supabase = False

    # C. Monitor de Dispositivos
    try:
        from src.services.monitor_service import DeviceMonitorManager
        
        # CORRECCIÓN AQUÍ: Usamos la bandera booleana en lugar de isinstance
        if supabase and is_real_supabase:
            monitor = DeviceMonitorManager(db_service=supabase, storage_service=storage)
            monitor.start()
            logger.info("✅ Monitor de dispositivos iniciado (Logueando a Supabase)")
        else:
            logger.warning("⚠️ Monitor no iniciado: Supabase no disponible o en modo Stub")
            
    except ImportError:
        logger.warning("⚠️ Módulo Monitor no encontrado.")
        monitor = None
    except Exception as e:
        logger.error(f"❌ Error iniciando el Monitor: {e}")
        monitor = None

    # ==========================================
    # 3. REGISTRO DE BLUEPRINTS
    # ==========================================
    try:
        from src.routes.api import bp as api_bp
        from src.routes.views import bp as views_bp
        # Importamos las rutas corregidas de AppSheet (Legacy)
        from src.routes.appsheet import bp as appsheet_bp 

        app.register_blueprint(api_bp)
        app.register_blueprint(views_bp)
        app.register_blueprint(appsheet_bp)
        
        logger.info("✅ Blueprints registrados")
    except Exception as e:
        logger.error(f"❌ Error registrando rutas: {e}")

    # ==========================================
    # 4. HEALTH CHECK
    # ==========================================
    @app.route('/health')
    def health_check():
        return {
            "status": "Argos System Online",
            "mode": "Supabase Production" if is_real_supabase else "Local Mode",
            "services": {
                "database_cloud": "ONLINE" if is_real_supabase else "OFFLINE",
                "monitor": "RUNNING" if monitor and getattr(monitor, 'running', False) else "STOPPED"
            }
        }

    return app
