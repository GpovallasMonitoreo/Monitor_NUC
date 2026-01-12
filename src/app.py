import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS

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

# 3. SERVICIOS E INYECCIÓN DE DEPENDENCIAS
# Imports de clases
from src.services.storage_service import StorageService
from src.services.alert_service import AlertService
from src.services.appsheet_service import AppSheetService
from src.services.monitor_service import DeviceMonitorManager
# Import del módulo contenedor global
import src 

# Paths de datos
data_dir = os.path.join(base_dir, 'data')
os.makedirs(data_dir, exist_ok=True)
db_path = os.path.join(data_dir, 'inventory_db.json')

print("⚙️ Inicializando servicios...")

# Inicializar servicios base
src.alerts = AlertService(app)
src.storage = StorageService(db_path, alert_service=src.alerts)
src.appsheet = AppSheetService()

# Inicializar Monitor (pasándole el servicio de AppSheet)
src.monitor = DeviceMonitorManager(src.appsheet)
src.monitor.start() # Arrancar hilo en segundo plano

print(f"✅ ARGOS: Storage en {db_path}")
print(f"✅ ARGOS: Monitor iniciado")

# 4. BLUEPRINTS
from src.routes.api import bp as api_bp
app.register_blueprint(api_bp)

from src.routes.views import bp as views_bp
app.register_blueprint(views_bp)

# 5. RUTAS GLOBALES
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
    return jsonify({
        "status": "Argos Online",
        "monitor": "RUNNING" if src.monitor.running else "STOPPED"
    })

# 6. ARRANQUE
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    # use_reloader=False evita que el hilo del monitor se duplique en dev
    app.run(host='0.0.0.0', port=port, use_reloader=False)
