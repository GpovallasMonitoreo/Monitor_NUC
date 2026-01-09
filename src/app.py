import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS

# --- CONFIGURACIÓN DE RUTAS ---
base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'src', 'templates')
static_dir = os.path.join(base_dir, 'src', 'static')

# Añadir la raíz al path para importaciones
sys.path.append(base_dir)

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# --- CONFIGURACIÓN ---
app.secret_key = os.environ.get('SECRET_KEY', 'argos_secret_key_dev_mode')
CORS(app)

# --- CARGA DE DOTENV ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- REGISTRO DE BLUEPRINTS (AQUÍ ESTÁ LA SOLUCIÓN) ---

# 1. API Blueprint
try:
    from src.routes.api import bp as api_bp
    app.register_blueprint(api_bp)
except Exception as e:
    print(f"⚠️ Error cargando API: {e}")

# 2. Views Blueprint (¡ESTO FALTABA!)
# Esto conecta tus rutas /monitor, /latency, etc.
try:
    from src.routes.views import bp as views_bp
    app.register_blueprint(views_bp)
except Exception as e:
    print(f"⚠️ Error cargando Vistas: {e}")


# --- RUTAS GLOBALES / AUTENTICACIÓN ---
# Mantenemos Login/Logout aquí porque son globales, 
# pero la ruta '/' la hemos delegado a views.py (home)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('views.home')) # Nota: ahora redirige al blueprint 'views'

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # TODO: Conectar a DB real
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
    return jsonify({"status": "Argos Online"})

# Manejador de error 404 para depuración
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404 # Si no tienes 404.html, devuelve texto simple

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
