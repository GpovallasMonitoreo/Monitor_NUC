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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response, send_from_directory, flash
from flask_cors import CORS
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURACIÓN DEL SISTEMA Y RUTAS ABSOLUTAS ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Obtenemos la ruta absoluta de ESTE archivo (app.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.info(f"📍 Directorio Base detectado: {BASE_DIR}")

# --- DETECCIÓN INTELIGENTE DE TEMPLATES ---
# Intenta encontrar la carpeta de templates automáticamente
def find_template_folder():
    # Posibles nombres de carpeta
    possible_folders = ['templates', 'template', 'Template', 'Templates']
    
    for folder in possible_folders:
        folder_path = os.path.join(BASE_DIR, folder)
        if os.path.exists(folder_path):
            logging.info(f"✅ Carpeta de templates encontrada: {folder}")
            return folder_path
    
    # Si no encuentra ninguna, busca en el directorio padre
    parent_dir = os.path.dirname(BASE_DIR)
    for folder in possible_folders:
        folder_path = os.path.join(parent_dir, folder)
        if os.path.exists(folder_path):
            logging.info(f"✅ Carpeta de templates encontrada en directorio padre: {folder}")
            return folder_path
    
    # Si aún no encuentra, crea una carpeta templates
    default_path = os.path.join(BASE_DIR, 'templates')
    os.makedirs(default_path, exist_ok=True)
    logging.warning(f"⚠️ No se encontró carpeta de templates. Creando: {default_path}")
    return default_path

TEMPLATE_DIR = find_template_folder()
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DATA_FILE = os.path.join(BASE_DIR, 'data.json')

logging.info(f"📂 Directorio Templates configurado: {TEMPLATE_DIR}")

# Verificación detallada
logging.info("🔍 Verificando estructura de archivos...")
if os.path.exists(TEMPLATE_DIR):
    items = os.listdir(TEMPLATE_DIR)
    logging.info(f"📁 Contenido de {TEMPLATE_DIR}: {items}")
    
    login_path = os.path.join(TEMPLATE_DIR, 'login.html')
    if os.path.exists(login_path):
        logging.info(f"✅ login.html encontrado: {login_path}")
    else:
        logging.error(f"❌ login.html NO encontrado en {TEMPLATE_DIR}")
        
        # Crear un login.html básico si no existe
        try:
            basic_login = """<!DOCTYPE html>
<html>
<head><title>Login Argos</title></head>
<body>
<h1>Login Argos (Autogenerado)</h1>
<form method="POST">
<input name="username" placeholder="Usuario"><br>
<input type="password" name="password" placeholder="Contraseña"><br>
<button type="submit">Ingresar</button>
</form>
<p>Por favor, sube el login.html correcto a: {}</p>
</body>
</html>""".format(TEMPLATE_DIR)
            
            with open(login_path, 'w') as f:
                f.write(basic_login)
            logging.info(f"📝 Se creó un login.html básico en {login_path}")
        except Exception as e:
            logging.error(f"❌ Error creando login.html: {e}")
else:
    logging.error(f"❌ CRÍTICO: Carpeta TEMPLATE_DIR no existe: {TEMPLATE_DIR}")

# Inicializamos Flask forzando las carpetas correctas
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

# Configuración de Entorno
FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
IS_PRODUCTION = FLASK_ENV == 'production'

app.config.update(
    SESSION_COOKIE_SAMESITE='None',
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    SECRET_KEY=os.environ.get('FLASK_SECRET_KEY', 'argos-clave-maestra-2026')
)
app.permanent_session_lifetime = timedelta(days=365)

CORS(app, supports_credentials=True, origins="*")

# Zona Horaria
try:
    TZ_CDMX = ZoneInfo("America/Mexico_City")
except ZoneInfoNotFoundError:
    TZ_CDMX = ZoneInfo("UTC")

# Usuarios (Hardcoded por seguridad básica)
USERS = { "admin": "password123", "gpovallas": "monitor2025", "Soporte01": "monitor2025" }

# --- 2. PERSISTENCIA DE DATOS (JSON) ---
data_store = {}     # Memoria RAM principal
alerted_pcs = {}    # Control de estado de alertas (para no spammear correos)
data_lock = Lock()  # Semáforo para hilos

def load_data_on_startup():
    """Carga la base de datos JSON al iniciar."""
    global data_store
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data_store = json.load(f)
                logging.info(f"✅ Base de datos cargada: {len(data_store)} equipos.")
        else:
            logging.info("ℹ️ No se encontró data.json, iniciando vacío.")
    except Exception as e:
        logging.error(f"⚠️ Error cargando datos: {e}")
        data_store = {}

def save_data_on_exit():
    """Guarda la base de datos JSON al apagar."""
    with data_lock:
        try:
            with open(DATA_FILE, 'w') as f:
                clean_data = {k: v for k, v in data_store.items()}
                json.dump(clean_data, f, indent=4)
            logging.info("✅ Datos guardados correctamente.")
        except Exception as e:
            logging.error(f"🔥 Error guardando datos: {e}")

# --- 3. SISTEMA DE CORREOS ---
EMAIL_ACCOUNTS = [
    {'sender': os.environ.get('EMAIL_SENDER_1'), 'password': os.environ.get('EMAIL_PASSWORD_1'), 'name': 'Argos Alerta 1'},
    {'sender': os.environ.get('EMAIL_SENDER_2'), 'password': os.environ.get('EMAIL_PASSWORD_2'), 'name': 'Argos Alerta 2'},
]
EMAIL_ACCOUNTS = [acc for acc in EMAIL_ACCOUNTS if acc['sender'] and acc['password']]

EMAIL_CONFIG = {
    'server': 'smtp.gmail.com',
    'port': 587,
    'recipients': ['incidencias.vallas@gpovallas.com'],
    'timeout_offline': 45
}

email_lock = Lock()
current_email_idx = 0

def get_smtp_account():
    global current_email_idx
    if not EMAIL_ACCOUNTS: return None
    with email_lock:
        acc = EMAIL_ACCOUNTS[current_email_idx]
        current_email_idx = (current_email_idx + 1) % len(EMAIL_ACCOUNTS)
    return acc

def send_email_alert(pc_name, alert_type, pc_data):
    account = get_smtp_account()
    if not account: return

    is_offline = (alert_type == 'offline')
    subject = f"🚨 ALERTA: {pc_name} Desconectado" if is_offline else f"✅ RESTAURADO: {pc_name} Online"
    color = "#d9534f" if is_offline else "#5cb85c"
    title = "PÉRDIDA DE CONEXIÓN" if is_offline else "CONEXIÓN RESTABLECIDA"
    now_str = datetime.now(TZ_CDMX).strftime('%d/%m/%Y %H:%M:%S')

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #ddd; border-radius: 8px;">
        <div style="background-color: {color}; color: white; padding: 20px; text-align: center;">
            <h2>{title}</h2>
        </div>
        <div style="padding: 20px;">
            <p><strong>Equipo:</strong> {pc_name}</p>
            <p><strong>Unidad:</strong> {pc_data.get('unit', 'Desconocida')}</p>
            <p><strong>IP Local:</strong> {pc_data.get('ip', 'N/A')}</p>
            <p><strong>Hora del evento:</strong> {now_str}</p>
            <hr>
            <p style="font-size: 12px; color: #777;">Reporte automático del Sistema Argos.</p>
        </div>
    </div>
    """

    msg = MIMEMultipart()
    msg['From'] = f"{account['name']} <{account['sender']}>"
    msg['To'] = ", ".join(EMAIL_CONFIG['recipients'])
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(EMAIL_CONFIG['server'], EMAIL_CONFIG['port']) as server:
            server.starttls()
            server.login(account['sender'], account['password'])
            server.send_message(msg)
        logging.info(f"📧 Correo enviado: {alert_type} - {pc_name}")
    except Exception as e:
        logging.error(f"🔥 Error enviando correo: {e}")

# --- 4. SEGURIDAD Y RUTAS ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if USERS.get(user) == pwd:
            session['user'] = user
            session.permanent = True
            return redirect(url_for('monitor'))
        else:
            flash('Credenciales Incorrectas', 'error')
    
    # Verificar que el template existe
    login_path = os.path.join(TEMPLATE_DIR, 'login.html')
    if not os.path.exists(login_path):
        # Crear un login temporal si no existe
        temp_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Login Argos - Debug</title></head>
        <body>
            <h1>⚠️ Sistema Argos - Debug</h1>
            <p>El archivo login.html no se encontró en: {login_path}</p>
            <p>Por favor, accede a <a href="/debug-argos">/debug-argos</a> para ver la estructura de archivos.</p>
            <p>BASE_DIR: {BASE_DIR}</p>
            <p>TEMPLATE_DIR: {TEMPLATE_DIR}</p>
            <hr>
            <h3>Login Temporal:</h3>
            <form method="POST">
                <input name="username" placeholder="Usuario" value="admin"><br>
                <input type="password" name="password" placeholder="Contraseña" value="password123"><br>
                <button type="submit">Ingresar</button>
            </form>
        </body>
        </html>
        """
        return temp_html
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 5. VISTAS DEL DASHBOARD (HTMLs) ---

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('monitor'))
    return redirect(url_for('login'))

@app.route('/monitor')
@login_required
def monitor():
    return render_template('monitor.html')

@app.route('/latency')
@login_required
def latency():
    return render_template('latency.html')

@app.route('/map')
@login_required
def map_view():
    return render_template('map.html')

# --- 6. API Y DEBUGGING ---

@app.route('/report', methods=['POST'])
def receive_report():
    try:
        data = request.json
        pc_name = data.get('pc_name')
        if not pc_name: return jsonify({"error": "No pc_name"}), 400

        now = datetime.now(TZ_CDMX)
        
        with data_lock:
            if alerted_pcs.get(pc_name) == 'offline':
                logging.info(f"🔄 {pc_name} ha vuelto ONLINE.")
                Thread(target=send_email_alert, args=(pc_name, 'online', data)).start()
                alerted_pcs[pc_name] = 'online'

            data['last_seen'] = now.timestamp()
            data['last_seen_str'] = now.strftime('%Y-%m-%d %H:%M:%S')
            if 'latency_ms' not in data: data['latency_ms'] = 0
            if 'unit' not in data: data['unit'] = "Sin Asignar"
            
            data_store[pc_name] = data

        return jsonify({"status": "received"}), 200
    except Exception as e:
        logging.error(f"Error en /report: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/live-data', methods=['GET'])
@login_required
def live_data():
    response_list = []
    now_ts = datetime.now(TZ_CDMX).timestamp()

    with data_lock:
        for pc_name, data in data_store.items():
            last_seen = data.get('last_seen', 0)
            diff = now_ts - last_seen
            pc_export = data.copy()
            
            if diff > EMAIL_CONFIG['timeout_offline']:
                pc_export['status'] = 'offline'
                pc_export['latency_ms'] = 0
                if alerted_pcs.get(pc_name) != 'offline':
                    logging.warning(f"🚨 {pc_name} ha caído OFFLINE.")
                    Thread(target=send_email_alert, args=(pc_name, 'offline', data)).start()
                    alerted_pcs[pc_name] = 'offline'
            else:
                pc_export['status'] = 'online'
                if alerted_pcs.get(pc_name) == 'offline':
                    alerted_pcs[pc_name] = 'online'

            response_list.append(pc_export)
    return jsonify(response_list)

@app.route('/download_csv')
@login_required
def download_csv():
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['PC Name', 'Unit', 'Status', 'IP', 'Latency (ms)', 'CPU %', 'RAM %', 'Temp', 'Last Seen'])
    with data_lock:
        for pc, d in data_store.items():
            cw.writerow([
                pc, d.get('unit', 'N/A'), d.get('status', 'unknown'), d.get('ip', 'N/A'),
                d.get('latency_ms', 0), d.get('cpu_load_percent', 0), d.get('ram_percent', 0),
                d.get('basic_metrics', {}).get('temp', 'N/A'), d.get('last_seen_str', '')
            ])
    output = Response(si.getvalue(), mimetype="text/csv")
    output.headers["Content-Disposition"] = "attachment; filename=reporte_argos.csv"
    return output

# --- RUTA DE DIAGNÓSTICO DE ARGOS ---
@app.route('/debug-argos')
def debug_files():
    """Muestra la estructura de archivos del servidor para debuggear."""
    output = []
    output.append(f"<h2>🔍 Diagnóstico del Sistema Argos</h2>")
    output.append(f"<p><strong>Directorio Actual (getcwd):</strong> {os.getcwd()}</p>")
    output.append(f"<p><strong>Archivo app.py:</strong> {os.path.abspath(__file__)}</p>")
    output.append(f"<p><strong>Directorio BASE calculado:</strong> {BASE_DIR}</p>")
    output.append(f"<p><strong>Directorio TEMPLATES configurado:</strong> {TEMPLATE_DIR}</p>")
    output.append(f"<p><strong>TEMPLATE_DIR existe:</strong> {os.path.exists(TEMPLATE_DIR)}</p>")
    
    if os.path.exists(TEMPLATE_DIR):
        items = os.listdir(TEMPLATE_DIR)
        output.append(f"<p><strong>Archivos en TEMPLATE_DIR ({len(items)}):</strong></p><ul>")
        for item in items:
            item_path = os.path.join(TEMPLATE_DIR, item)
            is_file = os.path.isfile(item_path)
            size = os.path.getsize(item_path) if is_file else 0
            output.append(f"<li>{item} {'📄' if is_file else '📁'} ({size} bytes)</li>")
        output.append("</ul>")
    
    output.append("<hr><h3>📁 Estructura del Proyecto (desde raíz):</h3>")
    
    # Listar desde el directorio raíz del proyecto en Render
    render_project_root = "/opt/render/project"
    if os.path.exists(render_project_root):
        for root, dirs, files in os.walk(render_project_root):
            level = root.replace(render_project_root, '').count(os.sep)
            if level > 2:  # Limitar profundidad
                continue
            indent = '&nbsp;' * 4 * level
            output.append(f"{indent}<b>[DIR] {os.path.basename(root) or 'ROOT'}/</b><br>")
            subindent = '&nbsp;' * 4 * (level + 1)
            for f in files[:10]:  # Mostrar solo primeros 10 archivos
                file_path = os.path.join(root, f)
                size = os.path.getsize(file_path)
                output.append(f"{subindent}{f} ({size} bytes)<br>")
            if len(files) > 10:
                output.append(f"{subindent}... y {len(files)-10} más<br>")
    else:
        # Si no está en Render, mostrar desde BASE_DIR
        for root, dirs, files in os.walk(BASE_DIR):
            level = root.replace(BASE_DIR, '').count(os.sep)
            if level > 2:
                continue
            indent = '&nbsp;' * 4 * level
            output.append(f"{indent}<b>[DIR] {os.path.basename(root) or 'ROOT'}/</b><br>")
            subindent = '&nbsp;' * 4 * (level + 1)
            for f in files[:10]:
                file_path = os.path.join(root, f)
                size = os.path.getsize(file_path)
                output.append(f"{subindent}{f} ({size} bytes)<br>")
    
    output.append("<hr><h3>🎯 Información de Flask:</h3>")
    output.append(f"<p><strong>template_folder configurado:</strong> {app.template_folder}</p>")
    output.append(f"<p><strong>static_folder configurado:</strong> {app.static_folder}</p>")
    
    return "<div style='font-family: monospace; background: #1a1a1a; color: #fff; padding: 20px;'>" + "".join(output) + "</div>"

# --- EJECUCIÓN ---
if __name__ == '__main__':
    load_data_on_startup()
    atexit.register(save_data_on_exit)
    port = int(os.environ.get('PORT', 10000))
    logging.info(f"✅ Servidor Argos Iniciado en puerto {port}")
    app.run(host='0.0.0.0', port=port)
