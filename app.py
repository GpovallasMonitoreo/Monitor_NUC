import os
import sys
from flask import Flask, render_template_string, request, session, redirect, jsonify

# ============================================
# 1. CONFIGURACIÓN BÁSICA
# ============================================
app = Flask(__name__)
app.secret_key = 'argos-secret-123'

# ============================================
# 2. DIAGNÓSTICO AL INICIAR
# ============================================
print("=" * 60)
print("🚀 ARGOS - DIAGNÓSTICO INICIAL")
print(f"📂 Directorio: {os.getcwd()}")
print("📁 Archivos en directorio actual:")

for item in os.listdir('.'):
    if os.path.isdir(item):
        print(f"  📁 {item}/")
        # Si es una carpeta de templates, mostrar contenido
        if item.lower() in ['templates', 'template']:
            try:
                files = os.listdir(item)
                print(f"    Contiene: {', '.join(files)}")
            except:
                pass
    else:
        print(f"  📄 {item}")

print("=" * 60)

# ============================================
# 3. HTML INLINE (NO necesita archivos!)
# ============================================
LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Argos Login</title>
    <style>
        body {
            background: #0f172a;
            color: white;
            font-family: Arial;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .login-box {
            background: #1e293b;
            padding: 30px;
            border-radius: 10px;
            text-align: center;
            width: 300px;
        }
        input {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: none;
            border-radius: 5px;
        }
        button {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            width: 100%;
        }
        .error {
            color: #ef4444;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>👁️ ARGOS</h2>
        <p>Sistema de Monitoreo</p>
        
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        
        <form method="POST">
            <input type="text" name="username" placeholder="Usuario" required>
            <input type="password" name="password" placeholder="Contraseña" required>
            <button type="submit">Ingresar</button>
        </form>
        
        <div style="margin-top: 20px; font-size: 12px; color: #94a3b8;">
            Usuarios:<br>
            admin / password123<br>
            gpovallas / monitor2025
        </div>
    </div>
</body>
</html>
"""

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Argos Dashboard</title>
    <style>
        body {
            background: #0f172a;
            color: white;
            font-family: Arial;
            margin: 0;
            padding: 20px;
        }
        .header {
            background: #1e293b;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .card {
            background: #1e293b;
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
        a {
            color: #3b82f6;
            text-decoration: none;
        }
        .online { color: #10b981; }
        .offline { color: #ef4444; }
    </style>
</head>
<body>
    <div class="header">
        <h1>👁️ ARGOS MONITOR</h1>
        <p>Bienvenido, {{ username }} | <a href="/logout">Cerrar sesión</a></p>
    </div>
    
    <div class="card">
        <h2>✅ Sistema Operativo</h2>
        <p>El servidor Argos está funcionando correctamente.</p>
        <p><strong>URL API:</strong> /report (POST) - Para clientes</p>
        <p><strong>URL Datos:</strong> /api/data (GET) - Para dashboard</p>
    </div>
    
    <div class="card">
        <h2>🔗 Enlaces útiles:</h2>
        <p><a href="/debug">/debug</a> - Información del sistema</p>
        <p><a href="/api/status">/api/status</a> - Estado del servicio</p>
    </div>
</body>
</html>
"""

DEBUG_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Diagnóstico Argos</title>
    <style>
        body {
            font-family: monospace;
            background: #0f172a;
            color: #e2e8f0;
            padding: 20px;
        }
        pre {
            background: #1e293b;
            padding: 20px;
            border-radius: 5px;
            overflow: auto;
        }
        .success { color: #10b981; }
        .error { color: #ef4444; }
    </style>
</head>
<body>
    <h1>🔧 DIAGNÓSTICO ARGOS</h1>
    
    <h2>📊 Información del Sistema</h2>
    <pre>{{ system_info }}</pre>
    
    <h2>📁 Estructura de Archivos</h2>
    <pre>{{ file_structure }}</pre>
    
    <h2>🎯 Acciones</h2>
    <p><a href="/">Inicio</a> | <a href="/login">Login</a> | <a href="/monitor">Dashboard</a></p>
</body>
</html>
"""

# ============================================
# 4. USUARIOS Y DATOS
# ============================================
USERS = {
    "admin": "password123",
    "gpovallas": "monitor2025",
    "Soporte01": "monitor2025"
}

data_store = {}

# ============================================
# 5. RUTAS PRINCIPALES
# ============================================
@app.route('/')
def home():
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
            # Mostrar error en la misma página
            return render_template_string(LOGIN_PAGE, error="Usuario o contraseña incorrectos")
    
    return render_template_string(LOGIN_PAGE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/monitor')
def monitor():
    if 'user' not in session:
        return redirect('/login')
    
    return render_template_string(DASHBOARD_PAGE, username=session['user'])

# ============================================
# 6. API ENDPOINTS
# ============================================
@app.route('/api/status')
def api_status():
    return jsonify({
        "status": "online",
        "service": "Argos Monitor",
        "version": "2.0",
        "timestamp": "2026-01-08T22:30:00Z"
    })

@app.route('/report', methods=['POST'])
def report():
    try:
        data = request.json
        pc_name = data.get('pc_name')
        
        if not pc_name:
            return jsonify({"error": "Se requiere pc_name"}), 400
        
        import datetime
        data['received_at'] = datetime.datetime.now().isoformat()
        data_store[pc_name] = data
        
        print(f"📡 Reporte recibido de {pc_name}")
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        print(f"❌ Error en /report: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/data')
def api_data():
    if 'user' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    return jsonify(list(data_store.values()))

# ============================================
# 7. RUTA DE DIAGNÓSTICO
# ============================================
@app.route('/debug')
def debug():
    import datetime
    
    # Información del sistema
    system_info = {
        "app_name": "Argos Monitor",
        "timestamp": datetime.datetime.now().isoformat(),
        "python_version": sys.version,
        "current_directory": os.getcwd(),
        "files_here": os.listdir('.'),
        "session_user": session.get('user'),
        "data_count": len(data_store),
        "on_render": 'RENDER' in os.environ
    }
    
    # Estructura de archivos
    file_structure_lines = []
    for item in os.listdir('.'):
        if os.path.isdir(item):
            file_structure_lines.append(f"📁 {item}/")
            try:
                subitems = os.listdir(item)
                for sub in subitems[:5]:
                    file_structure_lines.append(f"  └── {sub}")
                if len(subitems) > 5:
                    file_structure_lines.append(f"  └── ... y {len(subitems)-5} más")
            except:
                pass
        else:
            file_structure_lines.append(f"📄 {item}")
    
    return render_template_string(
        DEBUG_PAGE,
        system_info=str(system_info),
        file_structure='\n'.join(file_structure_lines)
    )

# ============================================
# 8. INICIAR SERVIDOR
# ============================================
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("✅ SERVIDOR LISTO")
    print("🔗 URL Principal: http://localhost:10000")
    print("🔗 Debug: http://localhost:10000/debug")
    print("👤 Login: admin / password123")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
