import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

# Variables globales accesibles por las rutas
storage = None
alerts = None

def create_app():
    app = Flask(__name__)
    
    app.config['DATA_FILE'] = os.path.join(os.getcwd(), 'data', 'inventory_db.json')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_key_argos_2026')

    from src.services.storage_service import StorageService
    from src.services.alert_service import AlertService

    global storage, alerts
    
    # 1. Inicializar Alertas
    alerts = AlertService(app)
    
    # 2. Inicializar Storage e inyectar el servicio de alertas
    storage = StorageService(app.config['DATA_FILE'], alert_service=alerts)

    # 3. Registrar Rutas
    from src.routes.api import bp as api_bp
    from src.routes.views import bp as views_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    return app