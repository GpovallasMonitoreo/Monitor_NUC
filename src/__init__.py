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
# Definimos las variables aquí para que puedan ser importadas desde otros módulos
# Ejemplo: 'from src import supabase'
storage = None   # Configuración local (JSON)
alerts = None    # Sistema de alertas
supabase = None  # Base de datos Nube (Logs y Métricas)
monitor = None   # Hilo de monitoreo en segundo plano

def create_app():
    """
    Fábrica de Aplicación: Crea y configura la instancia de Flask
    y conecta todos los servicios.
    """
    app = Flask(__name__)
    
    # Configuración básica
    app.secret_key = os.environ.get('SECRET_KEY', 'argos_dev_key_secure')
    
    # Habilitar CORS para permitir peticiones desde el frontend
    CORS(app)

    # Rutas base para archivos locales
    base_dir = os.path.abspath(os.path.dirname(__file__))
    # La DB local solo guardará configuración de equipos, no logs históricos
    db_path = os.path.join(base_dir, '..', 'data', 'inventory_config.json')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # ==========================================
    # 2. INICIALIZACIÓN DE SERVICIOS
    # ==========================================
    global storage, alerts, supabase, monitor

    logger.info("⚙️ Inicializando servicios de Argos (Supabase Edition)...")

    # A. Servicios Base (Alertas y Almacenamiento Local de Configuración)
    try:
        from src.services.alert_service import AlertService
        from src.services.storage_service import StorageService
        
        alerts = AlertService(app)
        # StorageService ahora se enfoca solo en guardar la lista de IPs y nombres
        storage = StorageService(db_path, alert_service=alerts)
        logger.info("✅ Servicios Locales (Alerts/Storage) iniciados")
    except Exception as e:
        logger.error(f"❌ Error crítico en servicios locales: {e}")

    # B. Supabase Service (NUEVO MOTOR DE BASE DE DATOS)
    # Importamos aquí para evitar ciclos
    from src.services.supabase_service import SupabaseService
    
    try:
        # Intentamos conectar con la nube
        supabase = SupabaseService()
        logger.info("✅ Supabase Service conectado correctamente")
    except Exception as e:
        logger.error(f"❌ Fallo al conectar con Supabase: {e}")
        logger.warning("⚠️ El sistema funcionará solo en modo local (sin historial en nube)")
        
        # Stub simple por si falla la conexión para que no rompa el monitor
        class SupabaseStub:
            def buffer_metric(self, *args, **kwargs): pass
            def get_device_history(self, *args, **kwargs): return []
            def run_nightly_cleanup(self): pass
        
        supabase = SupabaseStub()

    # C. Monitor de Dispositivos (Hilo de Fondo)
    try:
        from src.services.monitor_service import DeviceMonitorManager
        
        # IMPORTANTE: Ahora pasamos 'supabase' al monitor en lugar de 'appsheet'
        # El monitor debe ser actualizado para llamar a supabase.buffer_metric()
        if supabase and not isinstance(supabase, SupabaseStub):
            monitor = DeviceMonitorManager(db_service=supabase, storage_service=storage)
            monitor.start()
            logger.info("✅ Monitor de dispositivos iniciado (Logueando a Supabase)")
        else:
            logger.warning("⚠️ Monitor no iniciado: Supabase no está disponible")
            
    except ImportError:
        logger.warning("⚠️ Módulo Monitor no encontrado o con errores de importación.")
        monitor = None
    except Exception as e:
        logger.error(f"❌ Error iniciando el Monitor: {e}")
        monitor = None

    # ==========================================
    # 3. REGISTRO DE BLUEPRINTS (RUTAS)
    # ==========================================
    try:
        from src.routes.api import bp as api_bp
        from src.routes.views import bp as views_bp
        # Nota: Si aún tienes rutas viejas de appsheet, puedes mantenerlas o borrarlas
        # from src.routes.appsheet import bp as appsheet_bp 

        app.register_blueprint(api_bp)
        app.register_blueprint(views_bp)
        # app.register_blueprint(appsheet_bp)
        
        logger.info("✅ Blueprints registrados")
    except Exception as e:
        logger.error(f"❌ Error registrando rutas: {e}")

    # ==========================================
    # 4. RUTAS DE SISTEMA (Healthcheck)
    # ==========================================
    @app.route('/health')
    def health_check():
        """Verifica el estado de los componentes clave"""
        sb_status = "ONLINE"
        if hasattr(supabase, 'client') is False: 
            sb_status = "OFFLINE (Stub)"
            
        return {
            "status": "Argos System Online",
            "mode": "Supabase Production",
            "services": {
                "database_cloud": sb_status,
                "local_config": "OK" if storage else "ERROR",
                "monitor": "RUNNING" if monitor and getattr(monitor, 'running', False) else "STOPPED"
            }
        }

    return app
