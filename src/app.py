import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS

# 1. CONFIGURACIÓN DE RUTAS ABSOLUTAS
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir)

template_dir = os.path.join(base_dir, 'src', 'templates')
static_dir = os.path.join(base_dir, 'src', 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# 2. CONFIGURACIÓN BÁSICA
app.secret_key = os.environ.get('SECRET_KEY', 'argos_secret_key_dev_mode')
CORS(app)

# Cargar variables de entorno (Local)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 3. INICIALIZACIÓN DE SERVICIOS
from src.services.storage_service import StorageService
from src.services.alert_service import AlertService
# --- NUEVOS IMPORTS ---
from src.services.appsheet_service import AppSheetService
from src.services.monitor_service import DeviceMonitorManager
# ----------------------
import src 

# Definir ruta de la DB
data_dir = os.path.join(base_dir, 'data')
os.makedirs(data_dir, exist_ok=True)
db_path = os.path.join(data_dir, 'inventory_db.json')

# Inicializar y asignar a las variables globales de src
print("⚙️ Inicializando servicios centrales...")

src.alerts = AlertService(app)
src.storage = StorageService(db_path, alert_service=src.alerts)

# --- INICIALIZACIÓN DE APPSHEET Y MONITOR ---
# 1. Servicio base de conexión
src.appsheet = AppSheetService()

# 2. Gestor de monitoreo (Watchdog + Lógica de 15min)
# Le pasamos el servicio de appsheet
src.monitor = DeviceMonitorManager(src.appsheet)

# 3. ARRANCAR EL HILO DE FONDO
# Esto ejecutará el bucle de 15 min y el watchdog de 10 min en paralelo a Flask
src.monitor.start()
# ---------------------------------------------

print(f"✅ ARGOS: Storage inicializado en {db_path}")
print(f"✅ ARGOS: Monitor AppSheet iniciado en segundo plano")

# 4. REGISTRO DE BLUEPRINTS
from src.routes.api import bp as api_bp
app.register_blueprint(api_bp)

from src.routes.views import bp as views_bp
app.register_blueprint(views_bp)

# 5. RUTAS GLOBALES DE SISTEMA

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # TODO: Conectar con DB real si es necesario
        if username == 'gpovallas' and password == 'admin': 
            session['username'] = username
            return redirect(url_for('views.home'))
        else:
            return render_template('login.html', error="Credenciales inválidas")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/health')
def health():
    # Incluimos el estado del monitor en el health check
    monitor_status = "RUNNING" if src.monitor.running else "STOPPED"
    appsheet_status = "CONNECTED" if src.appsheet.is_available() else "DISCONNECTED"
    
    return jsonify({
        "status": "Argos Online", 
        "database": "OK" if src.storage else "ERROR",
        "monitor": monitor_status,
        "appsheet": appsheet_status
    })

# 6. INICIO DEL SERVIDOR
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    try:
        # use_reloader=False es importante en desarrollo para evitar
        # que el hilo del monitor se duplique al recargar código.
        app.run(host='0.0.0.0', port=port, use_reloader=False)
    except KeyboardInterrupt:
        print("🛑 Deteniendo servicios...")
        src.monitor.stop()
