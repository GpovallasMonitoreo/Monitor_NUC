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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError # Requiere Python 3.9+

from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response, send_from_directory
from flask_cors import CORS
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURACIÓN DEL SISTEMA ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
logging.info("✅ Servidor Argos Iniciado.")

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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')

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
    except Exception as e:
        logging.error(f"⚠️ Error cargando datos: {e}")
        data_store = {}

def save_data_on_exit():
    """Guarda la base de datos JSON al apagar."""
    with data_lock:
        try:
            with open(DATA_FILE, 'w') as f:
                # Limpiamos datos internos no serializables si los hubiera
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
# Filtrar cuentas vacías
EMAIL_ACCOUNTS = [acc for acc in EMAIL_ACCOUNTS if acc['sender'] and acc['password']]

EMAIL_CONFIG = {
    'server': 'smtp.gmail.com',
    'port': 587,
    'recipients': ['incidencias.vallas@gpovallas.com'],
    'timeout_offline': 45 # Segundos sin señal para considerar OFFLINE
}

email_lock = Lock()
current_email_idx = 0

def get_smtp_account():
    """Rota entre cuentas de correo para evitar bloqueos."""
    global current_email_idx
    if not EMAIL_ACCOUNTS: return None
    with email_lock:
        acc = EMAIL_ACCOUNTS[current_email_idx]
        current_email_idx = (current_email_idx + 1) % len(EMAIL_ACCOUNTS)
    return acc

def send_email_alert(pc_name, alert_type, pc_data):
    """Envía correos de desconexión o reconexión."""
    account = get_smtp_account()
    if not account: return

    is_offline = (alert_type == 'offline')
    subject = f"🚨 ALERTA: {pc_name} Desconectado" if is_offline else f"✅ RESTAURADO: {pc_name} Online"
    color = "#d9534f" if is_offline else "#5cb85c"
    title = "PÉRDIDA DE CONEXIÓN" if is_offline else "CONEXIÓN RESTABLECIDA"
    
    # Formatear hora
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
    return send_from_directory('static', filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if USERS.get(user) == pwd:
            session['user'] = user
            session.permanent = True
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 5. VISTAS DEL DASHBOARD (HTMLs) ---

@app.route('/')
@login_required
def index():
    # Redirección por defecto al Monitor Principal
    return redirect(url_for('monitor'))

@app.route('/monitor')
@login_required
def monitor():
    """Dashboard Principal con KPIs y Gráficas en Vivo."""
    return render_template('monitor.html')

@app.route('/latency')
@login_required
def latency():
    """Dashboard de Latencia y Fichas Técnicas."""
    return render_template('latency.html')

@app.route('/map')
@login_required
def map_view():
    return render_template('map.html')

# --- 6. API (COMUNICACIÓN AGENTE <-> SERVIDOR <-> FRONTEND) ---

@app.route('/report', methods=['POST'])
def receive_report():
    """Endpoint donde los NUCs envían sus datos (POST)."""
    try:
        data = request.json
        pc_name = data.get('pc_name')
        if not pc_name: return jsonify({"error": "No pc_name"}), 400

        now = datetime.now(TZ_CDMX)
        
        with data_lock:
            # Detectar RECONEXIÓN
            if alerted_pcs.get(pc_name) == 'offline':
                logging.info(f"🔄 {pc_name} ha vuelto ONLINE.")
                Thread(target=send_email_alert, args=(pc_name, 'online', data)).start()
                alerted_pcs[pc_name] = 'online'

            # Actualizar datos
            data['last_seen'] = now.timestamp()
            data['last_seen_str'] = now.strftime('%Y-%m-%d %H:%M:%S')
            
            # Asegurar campos para evitar errores en frontend
            if 'latency_ms' not in data: data['latency_ms'] = 0
            if 'unit' not in data: data['unit'] = "Sin Asignar" # Para BioBox/ViaVerde/Ecovallas
            
            data_store[pc_name] = data

        return jsonify({"status": "received"}), 200
    except Exception as e:
        logging.error(f"Error en /report: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/live-data', methods=['GET'])
@login_required
def live_data():
    """Endpoint que consume el Frontend (Monitor/Latency)."""
    response_list = []
    now_ts = datetime.now(TZ_CDMX).timestamp()

    with data_lock:
        for pc_name, data in data_store.items():
            # Calcular tiempo desde último reporte
            last_seen = data.get('last_seen', 0)
            diff = now_ts - last_seen
            
            # Copia para enviar
            pc_export = data.copy()
            
            # Lógica de DESCONEXIÓN
            if diff > EMAIL_CONFIG['timeout_offline']:
                pc_export['status'] = 'offline' # Forzar status offline para el frontend
                pc_export['latency_ms'] = 0     # Latencia 0 si está caído
                
                # Disparar alerta si no se ha alertado antes
                if alerted_pcs.get(pc_name) != 'offline':
                    logging.warning(f"🚨 {pc_name} ha caído OFFLINE.")
                    Thread(target=send_email_alert, args=(pc_name, 'offline', data)).start()
                    alerted_pcs[pc_name] = 'offline'
            else:
                pc_export['status'] = 'online'
                # Resetear alerta si estaba marcado como offline pero sigue reportando (caso raro)
                if alerted_pcs.get(pc_name) == 'offline':
                    alerted_pcs[pc_name] = 'online'

            response_list.append(pc_export)

    return jsonify(response_list)

@app.route('/download_csv')
@login_required
def download_csv():
    """Descarga reporte CSV."""
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['PC Name', 'Unit', 'Status', 'IP', 'Latency (ms)', 'CPU %', 'RAM %', 'Temp', 'Last Seen'])
    
    with data_lock:
        for pc, d in data_store.items():
            cw.writerow([
                pc, 
                d.get('unit', 'N/A'),
                d.get('status', 'unknown'),
                d.get('ip', 'N/A'),
                d.get('latency_ms', 0),
                d.get('cpu_load_percent', 0),
                d.get('ram_percent', 0),
                d.get('basic_metrics', {}).get('temp', 'N/A'), # Ajustar según tu payload
                d.get('last_seen_str', '')
            ])
            
    output = Response(si.getvalue(), mimetype="text/csv")
    output.headers["Content-Disposition"] = "attachment; filename=reporte_argos.csv"
    return output

# --- EJECUCIÓN ---
if __name__ == '__main__':
    load_data_on_startup()
    atexit.register(save_data_on_exit)
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
