import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
from routes.api import bp as api_bp  # Importamos el Blueprint desde la nueva ubicación

# --- CONFIGURACIÓN DE RUTAS ABSOLUTAS (Solución al TemplateNotFound) ---
# Esto garantiza que Flask sepa exactamente dónde está la carpeta del proyecto
base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'templates')
static_dir = os.path.join(base_dir, 'static')

# Inicialización de la App con rutas explícitas
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Necesario para que funcionen las sesiones (cookies de login)
# En producción, usa una variable de entorno. Para desarrollo, usamos una por defecto.
app.secret_key = os.environ.get('SECRET_KEY', 'argos_clave_secreta_desarrollo_123')

# Habilitar CORS (Cross-Origin Resource Sharing)
CORS(app)

# --- REGISTRO DE BLUEPRINTS ---
# Conectamos el cerebro (API) con el cuerpo (App principal)
app.register_blueprint(api_bp)

# --- RUTAS DE VISTA (FRONTEND) ---

@app.route('/')
def index():
    """
    Ruta principal (Dashboard).
    Verifica si el usuario está logueado.
    """
    if 'username' in session:
        # Si tienes un archivo templates/index.html, usa: return render_template('index.html', user=session['username'])
        # Por ahora, mantengo tu vista actual simple para que veas que funciona:
        return f"""
        <h1>👁️ ARGOS MONITOR</h1>
        <p>Bienvenido, {session['username']} | <a href='/logout'>Cerrar sesión</a></p>
        <hr>
        <h3>✅ Sistema Operativo</h3>
        <p>El servidor Argos está funcionando correctamente.</p>
        <p>URL API: /api/inventory/save (POST)</p>
        <p>URL Datos: <a href='/api/data'>/api/data</a> (GET)</p>
        """
    else:
        # Si no hay sesión, mandar al login
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Maneja el inicio de sesión.
    GET: Muestra el formulario HTML.
    POST: Procesa los datos.
    """
    if request.method == 'POST':
        # AQUÍ VA TU LÓGICA REAL DE VALIDACIÓN DE USUARIOS
        # Por simplicidad para el ejemplo:
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Ejemplo: Login "dummy" (cámbialo por validación real de BD)
        if username == "gpovallas" and password == "admin": 
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Credenciales inválidas")

    # Si es GET, mostramos el archivo login.html
    # ¡IMPORTANTE! Asegúrate de que login.html exista en la carpeta 'templates'
    try:
        return render_template('login.html')
    except Exception as e:
        return f"Error crítico: No se encuentra 'login.html' en {template_dir}. Detalles: {e}"

@app.route('/logout')
def logout():
    """Cierra la sesión del usuario."""
    session.pop('username', None)
    return redirect(url_for('login'))

# --- PUNTO DE ENTRADA ---
if __name__ == '__main__':
    # En local usa debug=True. En Render, Gunicorn se encarga de esto.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
