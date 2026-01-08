import os
import sys
import logging
from flask import Flask, render_template_string, request, session, redirect, jsonify

# ============================================================
# CONFIGURACIÓN BÁSICA
# ============================================================
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = 'argos-temp-key-123'

# ============================================================
# DIAGNÓSTICO INICIAL
# ============================================================
print("=" * 60)
print("🚀 ARGOS - DIAGNÓSTICO INICIAL")
print(f"📂 Directorio actual: {os.getcwd()}")
print(f"📄 Archivo actual: {__file__}")
print("=" * 60)

# Listar archivos
print("\n📁 CONTENIDO DEL DIRECTORIO:")
for item in os.listdir('.'):
    path = os.path.join('.', item)
    if os.path.isdir(path):
        print(f"  📁 {item}/")
        try:
            subitems = os.listdir(path)
            for sub in subitems[:5]:  # Mostrar solo 5
                print(f"    - {sub}")
            if len(subitems) > 5:
                print(f"    - ... y {len(subitems)-5} más")
        except:
            pass
    else:
        print(f"  📄 {item}")

# ============================================================
# HTML INLINE (NO DEPENDE DE TEMPLATES)
# ============================================================
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Argos Monitor - Login</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
        }
        .login-box {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            width: 90%;
            max-width: 400px;
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        input {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin-top: 10px;
        }
        button:hover {
            opacity: 0.9;
        }
        .error {
            color: red;
            text-align: center;
            margin: 10px 0;
        }
        .success {
            color: green;
            text-align: center;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>👁️ ARGOS MONITOR</h1>
        
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        
        {% if message %}
        <div class="success">{{ message }}</div>
        {% endif %}
        
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="Usuario" required>
            <input type="password" name="password" placeholder="Contraseña" required>
            <button type="submit">Ingresar</button>
        </form>
        
        <div style="margin-top: 20px; text-align: center; color: #666; font-size: 14px;">
            <strong>Usuarios de prueba:</strong><br>
            • admin / password123<br>
            • gpovallas / monitor2025
        </div>
        
        <div style="margin-top: 20px; text-align: center;">
            <a href="/debug" style="color: #667eea; text-decoration: none;">
                🔧 Ver información del sistema
            </a>
        </div>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Argos Monitor</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .btn {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin: 5px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .status-online { color: green; }
        .status-offline { color: red; }
    </style>
</head>
<body>
    <div class="header">
        <h1>👁️ ARGOS MONITOR - DASHBOARD</h1>
        <p>Bienvenido, {{ user }} | <a href="/logout" style="color: white;">Cerrar sesión</a></p>
    </div>
    
    <div class="grid">
        <div class="card">
            <h2>📊 Estado del Sistema</h2>
            <p><strong>Servidor:</strong> <span class="status-online">✅ OPERATIVO</span></p>
            <p><strong>Versión:</strong> 2.0 (Render Optimizado)</p>
            <p><strong>API Endpoints:</strong> Listos</p>
        </div>
        
        <div class="card">
            <h2>🎯 Acciones Rápidas</h2>
            <a href="/debug" class="btn">🔧 Diagnóstico</a>
            <a href="/api/status" class="btn">📡 Estado API</a>
            <a href="/download" class="btn">📥 Descargar CSV</a>
        </div>
    </div>
    
    <div class="card">
        <h2>📈 Datos en Tiempo Real</h2>
        <div id="data-container">
            <p>Cargando datos...</p>
        </div>
        <button onclick="loadData()" style="margin-top: 10px;">🔄 Actualizar</button>
    </div>
    
    <script>
        async function loadData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                let html = '<table style="width:100%; border-collapse:collapse;">';
                html += '<tr><th>Equipo</th><th>Estado</th><th>Última Conexión</th></tr>';
                
                if (data.length > 0) {
                    data.forEach(item => {
                        html += `<tr>
                            <td>${item.pc_name || 'N/A'}</td>
                            <td class="${item.status === 'online' ? 'status-online' : 'status-offline'}">
                                ${item.status === 'online' ? '✅ ONLINE' : '❌ OFFLINE'}
                            </td>
                            <td>${item.last_seen_str || 'N/A'}</td>
                        </tr>`;
                    });
                } else {
                    html += '<tr><td colspan="3">No hay equipos conectados</td></tr>';
                }
                
                html += '</table>';
                document.getElementById('data-container').innerHTML = html;
            } catch (error) {
                document.getElementById('data-container').innerHTML = 
                    '<p style="color:red;">Error cargando datos</p>';
            }
        }
        
        // Cargar datos al inicio
        loadData();
        // Actualizar cada 30 segundos
        setInterval(loadData, 30000);
    </script>
</body>
</html>
"""

DEBUG_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Diagnóstico Argos</title>
    <style>
        body { font-family: monospace; background: #0f172a; color: #e2e8f0; padding: 20px; }
        h1, h2 { color: #38bdf8; }
        .card { background: #1e293b; border: 1px solid #334155; padding: 20px; margin: 10px 0; border-radius: 8px; }
        pre { white-space: pre-wrap; }
        .success { color: #4ade80; }
        .error { color: #f87171; }
        .btn { background: #38bdf8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; }
    </style>
</head>
<body>
    <h1>🔧 DIAGNÓSTICO COMPLETO - ARGOS</h1>
    
    <div class="card">
        <h2>📊 INFORMACIÓN DEL SISTEMA</h2>
        <pre>{{ system_info }}</pre>
    </div>
    
    <div class="card">
        <h2>📁 ESTRUCTURA DE ARCHIVOS</h2>
        <pre>{{ file_tree }}</pre>
    </div>
    
    <div class="card">
        <h2>🎯 ACCIONES</h2>
        <a href="/" class="btn">🏠 Inicio</a>
        <a href="/login" class="btn">🔐 Login</a>
        <a href="/monitor" class="btn">📊 Dashboard</a>
        <a href="/api/status" class="btn">📡 Estado API</a>
    </div>
    
    <div class="card">
        <h2>🐛 SOLUCIÓN DE PROBLEMAS</h2>
        <p>Si el sistema no funciona:</p>
        <ol>
            <li>Verifica que app.py esté en la raíz del repositorio</li>
            <li>En Render, usa "Clear build cache & Deploy"</li>
            <li>Espera 2-3 minutos después del deploy</li>
            <li>Accede a /debug para ver el estado</li>
        </ol>
    </div>
</body>
</html>
"""

# ============================================================
# RUTAS PRINCIPALES
# ============================================================

USERS = {
    "admin": "password123",
    "gpovallas": "monitor2025",
    "Soporte01": "monitor2025"
}

data_store = {}

@app.route('/')
def index():
    if 'user' in session:
        return redirect('/monitor')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if USERS.get(username) == password:
            session['user'] = username
            return redirect('/monitor')
        else:
            return render_template_string(LOGIN_HTML, error="Usuario o contraseña incorrectos")
    
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/monitor')
def monitor():
    if 'user' not in session:
        return redirect('/login')
    
    return render_template_string(DASHBOARD_HTML, user=session['user'])

# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/api/status')
def api_status():
    return jsonify({
        "status": "online",
        "service": "Argos Monitor",
        "version": "2.0",
        "timestamp": "2026-01-08T22:00:00Z",
        "message": "Sistema operativo en Render"
    })

@app.route('/api/data')
def api_data():
    if 'user' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    # Datos de ejemplo
    import datetime
    sample_data = [
        {
            "pc_name": "PC-OFICINA",
            "status": "online",
            "last_seen_str": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "ip": "192.168.1.100",
            "cpu": 45,
            "ram": 67
        },
        {
            "pc_name": "PC-ALMACEN",
            "status": "offline",
            "last_seen_str": "2026-01-08 21:30:00",
            "ip": "192.168.1.101",
            "cpu": 0,
            "ram": 0
        }
    ]
    
    return jsonify(sample_data)

@app.route('/report', methods=['POST'])
def report():
    try:
        data = request.json
        pc_name = data.get('pc_name')
        
        if not pc_name:
            return jsonify({"error": "Se requiere pc_name"}), 400
        
        import datetime
        data['last_seen'] = datetime.datetime.now().timestamp()
        data['last_seen_str'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_store[pc_name] = data
        
        return jsonify({"status": "ok", "message": f"Reporte de {pc_name} recibido"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# RUTAS DE DIAGNÓSTICO
# ============================================================

@app.route('/debug')
def debug():
    import datetime
    
    # Información del sistema
    system_info = {
        "timestamp": datetime.datetime.now().isoformat(),
        "python_version": sys.version,
        "platform": sys.platform,
        "current_dir": os.getcwd(),
        "files_in_current_dir": os.listdir('.'),
        "session_user": session.get('user'),
        "data_store_count": len(data_store),
        "on_render": 'RENDER' in os.environ
    }
    
    # Estructura de archivos
    file_tree = []
    for root, dirs, files in os.walk('.', topdown=True):
        level = root.count(os.sep)
        indent = '  ' * level
        file_tree.append(f"{indent}📁 {os.path.basename(root) or '.'}")
        
        subindent = '  ' * (level + 1)
        for f in files[:10]:
            file_tree.append(f"{subindent}📄 {f}")
        if len(files) > 10:
            file_tree.append(f"{subindent}... ({len(files)-10} más)")
    
    return render_template_string(DEBUG_HTML, 
                                 system_info=str(system_info),
                                 file_tree='\n'.join(file_tree))

@app.route('/download')
def download():
    if 'user' not in session:
        return redirect('/login')
    
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Equipo', 'Estado', 'Última Conexión', 'IP', 'CPU %', 'RAM %'])
    
    for pc_name, data in data_store.items():
        writer.writerow([
            pc_name,
            data.get('status', 'unknown'),
            data.get('last_seen_str', 'N/A'),
            data.get('ip', 'N/A'),
            data.get('cpu_load_percent', 0),
            data.get('ram_percent', 0)
        ])
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=argos-report.csv"}
    )

# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("✅ SERVIDOR ARGOS INICIADO CORRECTAMENTE")
    print("🔗 Accede a: http://localhost:10000")
    print("🔗 Login: admin / password123")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
