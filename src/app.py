import os
import logging
import json
import time
import smtplib
import csv
import io
import atexit
from datetime import datetime, timedelta
from threading import Lock, Thread
from functools import wraps

from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response, send_from_directory, flash
from flask_cors import CORS
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ============================================================================
# CONFIGURACIÓN INICIAL CRÍTICA PARA RENDER
# ============================================================================

# Configurar logging primero
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# IMPORTANTE: En Render, el directorio puede ser diferente
# Primero determinamos dónde estamos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.info(f"🚀 Iniciando Argos en directorio: {BASE_DIR}")

# ============================================================================
# DETECCIÓN INTELIGENTE DE CARPETAS (PARA RENDER)
# ============================================================================

def setup_folders():
    """Configura las carpetas de templates y static automáticamente."""
    
    # Opciones posibles para templates
    template_options = [
        os.path.join(BASE_DIR, 'templates'),      # Estructura estándar Flask
        os.path.join(BASE_DIR, 'template'),       # Tu estructura
        os.path.join(os.path.dirname(BASE_DIR), 'templates'),  # Un nivel arriba
        os.path.join(os.path.dirname(BASE_DIR), 'template'),   # Un nivel arriba
        os.path.join(BASE_DIR, 'src', 'templates'),  # Si está en src/
        os.path.join(BASE_DIR, 'src', 'template'),   # Si está en src/
    ]
    
    # Buscar carpeta de templates
    template_dir = None
    for option in template_options:
        if os.path.exists(option):
            template_dir = option
            logging.info(f"✅ Carpeta de templates encontrada: {template_dir}")
            break
    
    # Si no se encuentra, crear una
    if not template_dir:
        template_dir = os.path.join(BASE_DIR, 'templates')
        os.makedirs(template_dir, exist_ok=True)
        logging.warning(f"⚠️ No se encontró carpeta de templates. Creando: {template_dir}")
    
    # Verificar/crear login.html
    login_path = os.path.join(template_dir, 'login.html')
    if not os.path.exists(login_path):
        logging.warning(f"⚠️ login.html no encontrado en {template_dir}. Creando uno básico...")
        create_basic_login(login_path)
    
    # Buscar carpeta static
    static_dir = None
    static_options = [
        os.path.join(BASE_DIR, 'static'),
        os.path.join(BASE_DIR, 'src', 'static'),
        os.path.join(os.path.dirname(BASE_DIR), 'static'),
    ]
    
    for option in static_options:
        if os.path.exists(option):
            static_dir = option
            logging.info(f"✅ Carpeta static encontrada: {static_dir}")
            break
    
    if not static_dir:
        static_dir = os.path.join(BASE_DIR, 'static')
        os.makedirs(static_dir, exist_ok=True)
        logging.info(f"📁 Carpeta static creada: {static_dir}")
    
    return template_dir, static_dir

def create_basic_login(filepath):
    """Crea un archivo login.html básico si no existe."""
    basic_login = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login | Sistema Argos</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: white;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 400px;
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo h2 {
            color: #333;
            font-weight: bold;
        }
        .alert {
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h2>👁️ ARGOS</h2>
            <p class="text-muted">Sistema de Monitoreo</p>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <form method="POST" action="/login">
            <div class="mb-3">
                <label for="username" class="form-label">Usuario</label>
                <input type="text" class="form-control" id="username" name="username" 
                       required autofocus placeholder="admin">
            </div>
            <div class="mb-3">
                <label for="password" class="form-label">Contraseña</label>
                <input type="password" class="form-control" id="password" name="password" 
                       required placeholder="password123">
            </div>
            <div class="d-grid gap-2">
                <button type="submit" class="btn btn-primary btn-lg">Ingresar</button>
            </div>
        </form>
        
        <div class="mt-4 text-center">
            <small class="text-muted">Usuarios: admin/password123 | gpovallas/monitor2025</small>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>'''
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(basic_login)
        logging.info(f"📄 login.html creado en: {filepath}")
    except Exception as e:
        logging.error(f"❌ Error creando login.html: {e}")

# Configurar carpetas
TEMPLATE_DIR, STATIC_DIR = setup_folders()
DATA_FILE = os.path.join(BASE_DIR, 'data.json')

# ============================================================================
# INICIALIZACIÓN DE FLASK
# ============================================================================

app = Flask(__name__, 
            template_folder=TEMPLATE_DIR,
            static_folder=STATIC_DIR)

# Configuración
app.config.update(
    SECRET_KEY=os.environ.get('FLASK_SECRET_KEY', 'argos-clave-segura-2026-render'),
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=30)
)

CORS(app, supports_credentials=True, origins="*")

# ============================================================================
# CONFIGURACIÓN DEL SISTEMA
# ============================================================================

# Usuarios del sistema
USERS = {
    "admin": "password123",
    "gpovallas": "monitor2025", 
    "Soporte01": "monitor2025"
}

# Zona horaria
try:
    from zoneinfo import ZoneInfo
    TZ_CDMX = ZoneInfo("America/Mexico_City")
except:
    import pytz
    TZ_CDMX = pytz.timezone("America/Mexico_City")

# Almacenamiento de datos
data_store = {}
alerted_pcs = {}
data_lock = Lock()

# ============================================================================
# FUNCIONES DE PERSISTENCIA
# ============================================================================

def load_data():
    """Carga datos desde el archivo JSON."""
    global data_store
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data_store = json.load(f)
            logging.info(f"📊 Datos cargados: {len(data_store)} equipos")
        else:
            logging.info("📝 Iniciando con almacenamiento vacío")
            data_store = {}
    except Exception as e:
        logging.error(f"❌ Error cargando datos: {e}")
        data_store = {}

def save_data():
    """Guarda datos en el archivo JSON."""
    with data_lock:
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump(data_store, f, indent=2)
            logging.info("💾 Datos guardados correctamente")
        except Exception as e:
            logging.error(f"❌ Error guardando datos: {e}")

# ============================================================================
# SISTEMA DE CORREOS
# ============================================================================

EMAIL_CONFIG = {
    'server': 'smtp.gmail.com',
    'port': 587,
    'timeout_offline': 45,
    'recipients': ['incidencias.vallas@gpovallas.com']
}

def send_email_alert(pc_name, alert_type, pc_data):
    """Envía alertas por correo."""
    # Esta función se implementará cuando configures los emails
    logging.info(f"📧 Simulando envío de correo: {alert_type} - {pc_name}")
    return True

# ============================================================================
# DECORADORES Y UTILIDADES
# ============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# RUTAS PRINCIPALES
# ============================================================================

@app.route('/')
def index():
    """Página principal - redirige a login o monitor."""
    if 'user' in session:
        return redirect(url_for('monitor'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if USERS.get(username) == password:
            session['user'] = username
            session.permanent = True
            logging.info(f"✅ Usuario autenticado: {username}")
            return redirect(url_for('monitor'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
            logging.warning(f"❌ Intento de login fallido: {username}")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Cerrar sesión."""
    session.clear()
    return redirect(url_for('login'))

@app.route('/monitor')
@login_required
def monitor():
    """Dashboard principal."""
    return render_template('monitor.html')

@app.route('/latency')
@login_required
def latency():
    """Página de latencia."""
    return render_template('latency.html')

@app.route('/map')
@login_required
def map_view():
    """Mapa de equipos."""
    return render_template('map.html')

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/report', methods=['POST'])
def receive_report():
    """Recibe reportes de los clientes."""
    try:
        data = request.json
        pc_name = data.get('pc_name')
        
        if not pc_name:
            return jsonify({"error": "Se requiere pc_name"}), 400
        
        now = datetime.now(TZ_CDMX)
        
        with data_lock:
            # Registrar conexión
            data['last_seen'] = now.timestamp()
            data['last_seen_str'] = now.strftime('%Y-%m-%d %H:%M:%S')
            data['status'] = 'online'
            
            # Manejar alertas
            if alerted_pcs.get(pc_name) == 'offline':
                logging.info(f"🔄 {pc_name} reconectado")
                Thread(target=send_email_alert, args=(pc_name, 'online', data)).start()
                alerted_pcs[pc_name] = 'online'
            
            # Guardar datos
            data_store[pc_name] = data
        
        return jsonify({"status": "ok", "message": "Reporte recibido"}), 200
        
    except Exception as e:
        logging.error(f"❌ Error en /report: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/live-data')
@login_required
def live_data():
    """Devuelve datos en tiempo real para el dashboard."""
    now_ts = datetime.now(TZ_CDMX).timestamp()
    response_data = []
    
    with data_lock:
        for pc_name, data in data_store.items():
            pc_data = data.copy()
            last_seen = pc_data.get('last_seen', 0)
            
            # Verificar si está offline
            if (now_ts - last_seen) > EMAIL_CONFIG['timeout_offline']:
                pc_data['status'] = 'offline'
                
                if alerted_pcs.get(pc_name) != 'offline':
                    logging.warning(f"🚨 {pc_name} offline")
                    Thread(target=send_email_alert, args=(pc_name, 'offline', pc_data)).start()
                    alerted_pcs[pc_name] = 'offline'
            else:
                pc_data['status'] = 'online'
                if alerted_pcs.get(pc_name) == 'offline':
                    alerted_pcs[pc_name] = 'online'
            
            response_data.append(pc_data)
    
    return jsonify(response_data)

# ============================================================================
# RUTAS DE DIAGNÓSTICO Y UTILIDAD
# ============================================================================

@app.route('/debug')
def debug():
    """Página de diagnóstico del sistema."""
    info = {
        "app_root": app.root_path,
        "template_folder": app.template_folder,
        "static_folder": app.static_folder,
        "base_dir": BASE_DIR,
        "template_dir": TEMPLATE_DIR,
        "static_dir": STATIC_DIR,
        "data_file": DATA_FILE,
        "data_file_exists": os.path.exists(DATA_FILE),
        "login_html_exists": os.path.exists(os.path.join(TEMPLATE_DIR, 'login.html')),
        "users_registered": len(USERS),
        "equipos_monitorizados": len(data_store),
        "python_version": os.sys.version,
        "flask_env": os.environ.get('FLASK_ENV', 'No configurado'),
        "render": True if 'RENDER' in os.environ else False
    }
    
    # Listar archivos
    files_info = []
    for root, dirs, files in os.walk(BASE_DIR, topdown=True):
        level = root.replace(BASE_DIR, '').count(os.sep)
        indent = ' ' * 4 * level
        files_info.append(f"{indent}📁 {os.path.basename(root) or 'ROOT'}/")
        
        subindent = ' ' * 4 * (level + 1)
        for f in files[:10]:  # Mostrar solo 10 archivos por carpeta
            files_info.append(f"{subindent}📄 {f}")
        if len(files) > 10:
            files_info.append(f"{subindent}... y {len(files)-10} más")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🔧 Debug - Sistema Argos</title>
        <style>
            body {{ font-family: monospace; background: #0f172a; color: #e2e8f0; padding: 20px; }}
            h1, h2 {{ color: #38bdf8; }}
            .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; margin: 10px 0; }}
            .success {{ color: #4ade80; }}
            .error {{ color: #f87171; }}
            .warning {{ color: #fbbf24; }}
            .file-tree {{ background: #0f172a; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            pre {{ white-space: pre-wrap; }}
        </style>
    </head>
    <body>
        <h1>🔧 Sistema Argos - Diagnóstico</h1>
        
        <div class="card">
            <h2>📋 Información del Sistema</h2>
            <pre>{json.dumps(info, indent=2, ensure_ascii=False)}</pre>
        </div>
        
        <div class="card">
            <h2>📁 Estructura de Archivos</h2>
            <div class="file-tree">
                <pre>{"\n".join(files_info)}</pre>
            </div>
        </div>
        
        <div class="card">
            <h2>🔗 Enlaces</h2>
            <ul>
                <li><a href="/login" style="color: #38bdf8;">/login</a> - Página de login</li>
                <li><a href="/monitor" style="color: #38bdf8;">/monitor</a> - Dashboard (requiere login)</li>
                <li><a href="/api/live-data" style="color: #38bdf8;">/api/live-data</a> - API de datos</li>
            </ul>
        </div>
        
        <div class="card">
            <h2>🔄 Acciones</h2>
            <form action="/login" method="POST" style="margin-top: 10px;">
                <input type="hidden" name="username" value="admin">
                <input type="hidden" name="password" value="password123">
                <button type="submit" style="background: #38bdf8; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                    🔓 Login Automático (admin)
                </button>
            </form>
        </div>
    </body>
    </html>
    """
    
    return html

@app.route('/api/status')
def status():
    """Endpoint de estado para monitoreo."""
    return jsonify({
        "status": "online",
        "service": "Argos Monitor",
        "version": "2.0",
        "timestamp": datetime.now(TZ_CDMX).isoformat(),
        "equipos": len(data_store),
        "online": sum(1 for d in data_store.values() 
                     if (datetime.now(TZ_CDMX).timestamp() - d.get('last_seen', 0)) < 60)
    })

@app.route('/download-csv')
@login_required
def download_csv():
    """Descarga un reporte CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    writer.writerow(['Equipo', 'Unidad', 'Estado', 'Última Conexión', 'IP', 'Latencia', 'CPU %', 'RAM %'])
    
    with data_lock:
        for pc_name, data in data_store.items():
            writer.writerow([
                pc_name,
                data.get('unit', 'N/A'),
                data.get('status', 'unknown'),
                data.get('last_seen_str', 'N/A'),
                data.get('ip', 'N/A'),
                data.get('latency_ms', 0),
                data.get('cpu_load_percent', 0),
                data.get('ram_percent', 0)
            ])
    
    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=argos-report.csv"}
    )
    
    return response

# ============================================================================
# MANEJO DE ARCHIVOS ESTÁTICOS
# ============================================================================

@app.route('/static/<path:filename>')
def static_files(filename):
    """Sirve archivos estáticos."""
    return send_from_directory(STATIC_DIR, filename)

# ============================================================================
# INICIALIZACIÓN Y EJECUCIÓN
# ============================================================================

# Registrar funciones de limpieza
atexit.register(save_data)

if __name__ == '__main__':
    # Cargar datos al iniciar
    load_data()
    
    # Información de inicio
    logging.info("=" * 60)
    logging.info("🚀 INICIANDO SISTEMA ARGOS v2.0")
    logging.info(f"📂 Templates: {TEMPLATE_DIR}")
    logging.info(f"📁 Static: {STATIC_DIR}")
    logging.info(f"📊 Datos: {len(data_store)} equipos cargados")
    logging.info("=" * 60)
    
    # Obtener puerto de Render
    port = int(os.environ.get('PORT', 10000))
    
    # Iniciar servidor
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.environ.get('FLASK_ENV') == 'development'
    )
