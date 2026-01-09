import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DE RUTAS ABSOLUTAS (La Solución al Error)
# ---------------------------------------------------------
# Obtenemos la ruta donde está este archivo app.py (La raíz del proyecto)
base_dir = os.path.abspath(os.path.dirname(__file__))

# Definimos explícitamente dónde están los templates y static dentro de 'src'
template_dir = os.path.join(base_dir, 'src', 'templates')
static_dir = os.path.join(base_dir, 'src', 'static')

# ---------------------------------------------------------
# 2. INICIALIZACIÓN DE FLASK
# ---------------------------------------------------------
# Le decimos a Flask: "No busques aquí, busca en src/templates"
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# Configuración básica
app.secret_key = os.environ.get('SECRET_KEY', 'argos_secret_key_dev_mode')
CORS(app)

# ---------------------------------------------------------
# 3. IMPORTACIÓN DE TU LÓGICA (BLUEPRINTS)
# ---------------------------------------------------------
# Agregamos la raíz al path para poder importar 'src' sin problemas
sys.path.append(base_dir)

try:
    # Intenta cargar dotenv si existe (local), si no, sigue (producción)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Importamos el Blueprint de la API que arreglamos antes
# Asegúrate de que src/routes/api.py tenga: bp = Blueprint('api', __name__, url_prefix='/api')
try:
    from src.routes.api import bp as api_bp
    app.register_blueprint(api_bp)
except Exception as e:
    print(f"⚠️ Advertencia: No se pudo cargar la API: {e}")

# ---------------------------------------------------------
# 4. RUTAS VISUALES (FRONTEND)
# ---------------------------------------------------------

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    # Si tienes un dashboard.html en src/templates/inventory/ o src/templates/
    # Ajusta la ruta del template según corresponda. 
    # Viendo tu estructura, parece que tienes 'dashboard.html' directo en templates.
    return render_template('dashboard.html', user=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # --- LÓGICA DE VALIDACIÓN ---
        # TODO: Conectar esto con tu base de datos real
        if username == 'gpovallas' and password == 'admin': 
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Credenciales inválidas")

    # Flask ahora buscará esto en MONITOR-ENTERPRISE-MAIN/src/templates/login.html
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/health')
def health():
    return jsonify({"status": "Argos Online", "template_path": template_dir})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
