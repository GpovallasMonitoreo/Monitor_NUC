# src/__init__.py
import os
import logging
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# Configurar Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# ==========================================
# 1. INSTANCIAS GLOBALES (SINGLETONS)
# ==========================================
# Se definen aquí como None y se pueblan en create_app
storage = None
alerts = None
appsheet = None
monitor = None

def create_app():
    """Patrón de Fábrica de Aplicación"""
    app = Flask(__name__)
    
    # Configuración
    app.secret_key = os.environ.get('SECRET_KEY', 'argos_dev_key')
    CORS(app)

    # Rutas base
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, '..', 'data', 'inventory_db.json')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # ==========================================
    # 2. INICIALIZACIÓN DE SERVICIOS
    # ==========================================
    global storage, alerts, appsheet, monitor

    logger.info("⚙️ Inicializando servicios centrales...")

    # A. Servicios Base (Alerts & Storage)
    from src.services.alert_service import AlertService
    from src.services.storage_service import StorageService
    
    alerts = AlertService(app)
    storage = StorageService(db_path, alert_service=alerts)

    # B. AppSheet Service (Con manejo de error integrado)
    from src.services.appsheet_service import AppSheetService, AppSheetStub
    try:
        appsheet = AppSheetService()
        logger.info(f"✅ AppSheet Service iniciado. Estado: {appsheet.get_status_info()}")
    except Exception as e:
        logger.error(f"❌ Fallo al iniciar AppSheet: {e}")
        appsheet = AppSheetStub() # Degradación elegante

    # C. Monitor (Opcional)
    try:
        from src.services.monitor_service import DeviceMonitorManager
        if appsheet.enabled:
            monitor = DeviceMonitorManager(appsheet)
            monitor.start()
            logger.info("✅ Monitor de dispositivos iniciado")
        else:
            logger.warning("⚠️ Monitor en pausa: AppSheet deshabilitado")
    except ImportError:
        logger.warning("⚠️ Módulo Monitor no encontrado, continuando sin él.")
        monitor = None

    # ==========================================
    # 3. REGISTRO DE BLUEPRINTS (RUTAS)
    # ==========================================
    from src.routes.appsheet import bp as appsheet_bp
    from src.routes.api import bp as api_bp
    from src.routes.views import bp as views_bp

    app.register_blueprint(appsheet_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    # Healthcheck Global
    @app.route('/health')
    def health_check():
        return {
            "status": "online",
            "services": {
                "storage": "OK" if storage else "ERROR",
                "appsheet": "OK" if appsheet.enabled else "DISABLED"
            }
        }

    return app
