import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS

# --- IMPORTACIÓN DEL BLUEPRINT ---
# Como app.py está en 'src' y api.py en 'src/routes', importamos así:
try:
    from routes.api import bp as api_bp
except ImportError as e:
    # Fallback por si ejecutas desde fuera de la carpeta src
    from src.routes.api import bp as api_bp

# Configuración de carpetas para que Flask encuentre el login.html
# Se asume que la carpeta 'templates' está al mismo nivel que app.py
base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'templates')
static_dir = os.path.join(base_dir, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# --- CONFIGURACIÓN ---
app.secret_key = os.environ.get('SECRET_KEY', 'argos_secret_key_dev_mode') # Necesario para la sesión
CORS(app) # Permite peticiones externas si es necesario

# --- REGISTRO DE BLUEPRINTS ---
app.register_blueprint(api_bp)

# --- RUTAS DE VISTA (Frontend) ---

@app.route('/')
def index():
    """Panel principal. Protegido por sesión."""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Aquí renderizamos tu dashboard. 
    # Si tienes un archivo index.html úsalo: return render_template('index.html', user=session['username'])
    # Por ahora, mantengo lo que ya te funcionaba (HTML directo o template básico):
    return f"""
    <h1>👁️ ARGOS MONITOR</h1>
    <p>Bienvenido, {session['username']} | <a href='/logout'>Cerrar sesión</a></p>
    <hr>
    <h3>✅ Sistema Operativo</h3>
    <p>El servidor Argos está funcionando correctamente.</p>
    <p>URL API: <a href='/api/data'>/api/data</a></p>
    """

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Manejo del inicio de sesión."""
    # Si ya está logueado, mandar al inicio
    if 'username' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Lógica simple de autenticación
        username = request.form.get('username')
        password = request.form.get('password')
        
        # AQUÍ VALIDAS TUS USUARIOS
        # Ejemplo básico: usuario 'gpovallas', contraseña 'admin'
        if username == 'gpovallas' and password == 'admin': # ¡Cambia esto por DB o env vars!
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Credenciales inválidas")

    # Si es GET, mostramos el formulario
    # IMPORTANTE: Asegúrate que 'login.html' exista en src/templates/
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Cierra la sesión y limpia la cookie."""
    session.pop('username', None)
    return redirect(url_for('login'))

# --- VERIFICACIÓN DE ESTADO ---
@app.route('/health')
def health_check():
    return jsonify({"status": "ok", "service": "Argos Server"}), 200

if __name__ == '__main__':
    # En producción (Render), Gunicorn se encarga de esto, pero útil para local
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
