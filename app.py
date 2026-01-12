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
from src.services.appsheet_service import AppSheetService
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

# 3. AppSheet (Nube)
src.appsheet = AppSheetService()

# 4. Monitor (Hilo de fondo)
if src.appsheet.enabled:
    src.monitor = DeviceMonitorManager(src.appsheet)
    src.monitor.start() # Iniciar el hilo
else:
    src.monitor = None
    logger.info("⚠️ Monitor no iniciado porque AppSheet está deshabilitado")

logger.info(f"✅ ARGOS: Storage inicializado en {db_path}")

# 4. BLUEPRINTS
# Registramos las rutas DESPUÉS de haber inicializado los servicios
from src.routes.api import bp as api_bp
app.register_blueprint(api_bp)

from src.routes.views import bp as views_bp
app.register_blueprint(views_bp)

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
    monitor_status = "RUNNING" if (src.monitor and src.monitor.running) else "STOPPED"
    return jsonify({
        "status": "Argos Online",
        "monitor": monitor_status,
        "appsheet_enabled": src.appsheet.enabled if src.appsheet else False
    })

# 6. ARRANQUE
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)
