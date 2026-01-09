import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS

# 1. CONFIGURACIÓN DE RUTAS ABSOLUTAS
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir) # Crucial para que Python encuentre 'src'

template_dir = os.path.join(base_dir, 'src', 'templates')
static_dir = os.path.join(base_dir, 'src', 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# 2. CONFIGURACIÓN BÁSICA
app.secret_key = os.environ.get('SECRET_KEY', 'argos_secret_key_dev_mode')
CORS(app)

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 3. INICIALIZACIÓN DE SERVICIOS (SOLUCIÓN AL ERROR 500)
# Importamos las clases de servicios
from src.services.storage_service import StorageService
from src.services.alert_service import AlertService
# Importamos el módulo src para inyectarle las variables
import src 

# Definir ruta de la DB
data_dir = os.path.join(base_dir, 'data')
os.makedirs(data_dir, exist_ok=True)
db_path = os.path.join(data_dir, 'inventory_db.json')

# Inicializar y asignar a las variables globales de src
# Esto hace que cuando api.py haga "from src import storage", ya tenga datos.
src.alerts = AlertService(app)
src.storage = StorageService(db_path, alert_service=src.alerts)

print(f"✅ ARGOS: Storage inicializado en {db_path}")

# 4. REGISTRO DE BLUEPRINTS (SOLUCIÓN AL ERROR 404)
# Quitamos el try/except para ver errores reales si existen

from src.routes.api import bp as api_bp
app.register_blueprint(api_bp)
print("✅ ARGOS: API Blueprint registrado")

from src.routes.views import bp as views_bp
app.register_blueprint(views_bp)
print("✅ ARGOS: Views Blueprint registrado")


# 5. RUTAS GLOBALES DE SISTEMA (Login/Logout)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está logueado, ir al home (manejado por views.py)
    if 'username' in session:
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # TODO: Lógica real de usuarios
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
    # Verificación de salud del sistema
    status_db = "OK" if src.storage else "ERROR"
    return jsonify({"status": "Argos Online", "database": status_db})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
