import os
from flask import Flask

# --- BLOQUE DE SEGURIDAD PARA DOTENV ---
# Intentamos cargar dotenv, pero si no está instalado (o estamos en producción sin archivo .env),
# el sistema no debe colapsar. Simplemente seguimos adelante.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Esto ocurre si falta la librería 'python-dotenv'.
    # En producción es aceptable si las variables ya están en el sistema.
    pass 

# Variables globales accesibles por las rutas
storage = None
alerts = None

def create_app():
    app = Flask(__name__)
    
    # Configuración de rutas de archivos
    # Usamos os.path.abspath para evitar errores de rutas relativas en Linux
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Asumiendo que 'data' está al mismo nivel que la carpeta 'src'
    # Ajusta '..' si 'data' está dentro de src o fuera.
    data_dir = os.path.join(os.path.dirname(base_dir), 'data') 
    
    # Crear carpeta data si no existe (Prevención de errores)
    os.makedirs(data_dir, exist_ok=True)
    
    app.config['DATA_FILE'] = os.path.join(data_dir, 'inventory_db.json')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_key_argos_2026')

    # Importaciones diferidas para evitar referencias circulares
    # Nota: Asegúrate de que los services existan en src/services/
    from src.services.storage_service import StorageService
    from src.services.alert_service import AlertService

    global storage, alerts
    
    # 1. Inicializar Alertas
    alerts = AlertService(app)
    
    # 2. Inicializar Storage e inyectar el servicio de alertas
    storage = StorageService(app.config['DATA_FILE'], alert_service=alerts)

    # 3. Registrar Rutas
    # Envolvemos en try/except para evitar errores si la estructura de carpetas varía
    try:
        from src.routes.api import bp as api_bp
        from src.routes.views import bp as views_bp
    except ImportError:
        # Fallback por si Python no reconoce 'src' como paquete raíz
        from routes.api import bp as api_bp
        from routes.views import bp as views_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    return app
