import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
import logging
from datetime import datetime, timedelta

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. CONFIGURACIÓN DE RUTAS ABSOLUTAS
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(base_dir) # Crucial para que Python encuentre 'src'

template_dir = os.path.join(base_dir, 'src', 'templates')
static_dir = os.path.join(base_dir, 'src', 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# 2. CONFIGURACIÓN BÁSICA
app.secret_key = os.environ.get('SECRET_KEY', 'argos_secret_key_dev_mode')
CORS(app)

# Cargar variables de entorno (Local)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 3. INICIALIZACIÓN DE SERVICIOS
# Importamos las clases de servicios
from src.services.storage_service import StorageService
from src.services.alert_service import AlertService
# Importamos el módulo src para inyectarle las variables globales
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

# 4. INICIALIZAR CLIENTE APPSHEET (si está configurado)
try:
    from src.services.appsheet_service import AppSheetService
    appsheet_enabled = os.environ.get('APPSHEET_ENABLED', 'false').lower() == 'true'
    
    if appsheet_enabled:
        src.appsheet = AppSheetService()
        logger.info("✅ AppSheet Service inicializado")
    else:
        src.appsheet = None
        logger.info("ℹ️ AppSheet deshabilitado (APPSHEET_ENABLED=false)")
        
except ImportError as e:
    src.appsheet = None
    logger.warning(f"⚠️ AppSheet Service no disponible: {e}")
except Exception as e:
    src.appsheet = None
    logger.error(f"❌ Error inicializando AppSheet: {e}")

# 5. REGISTRO DE BLUEPRINTS
# Registramos API y Vistas
from src.routes.api import bp as api_bp
app.register_blueprint(api_bp)

from src.routes.views import bp as views_bp
app.register_blueprint(views_bp)

# 6. RUTAS GLOBALES DE SISTEMA (Login/Logout/Health)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está logueado, ir al home
    if 'username' in session:
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Validación de usuario
        # TODO: Conectar con DB real si es necesario
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
    # Verificación de salud del sistema para Render
    status_db = "OK" if src.storage else "ERROR"
    status_appsheet = "ENABLED" if src.appsheet and src.appsheet.is_available() else "DISABLED"
    
    return jsonify({
        "status": "Argos Online", 
        "database": status_db,
        "appsheet": status_appsheet,
        "timestamp": datetime.now().isoformat()
    })

# 7. ENDPOINTS DE APPSHEET

@app.route('/api/appsheet/sync', methods=['POST'])
def sync_to_appsheet():
    """Sincronizar datos actuales con AppSheet"""
    try:
        if not src.appsheet:
            return jsonify({
                "status": "error",
                "message": "AppSheet no está configurado"
            }), 400
        
        # Obtener datos actuales del sistema
        all_devices = src.storage.get_all_devices()
        
        if not all_devices:
            return jsonify({
                "status": "error",
                "message": "No hay dispositivos para sincronizar"
            }), 400
        
        results = []
        success_count = 0
        error_count = 0
        
        for device in all_devices.values():
            try:
                # Sincronizar dispositivo
                device_result = src.appsheet.upsert_device(device)
                
                # Sincronizar métricas actuales
                latency_result = src.appsheet.add_latency_record(device)
                
                # Verificar alertas
                if device.get('status') == 'critical' or device.get('cpu_load_percent', 0) > 90:
                    alert_msg = f"CPU al {device.get('cpu_load_percent', 0)}%"
                    src.appsheet.add_alert(
                        device, 
                        'high_cpu', 
                        alert_msg, 
                        'high'
                    )
                
                if device.get('temperature', 0) > 70:
                    alert_msg = f"Temperatura: {device.get('temperature', 0)}°C"
                    src.appsheet.add_alert(
                        device, 
                        'high_temp', 
                        alert_msg, 
                        'medium'
                    )
                
                results.append({
                    'pc_name': device.get('pc_name', 'Unknown'),
                    'device_sync': 'success' if device_result else 'error',
                    'latency_sync': 'success' if latency_result else 'error'
                })
                
                if device_result and latency_result:
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"Error sincronizando dispositivo {device.get('pc_name')}: {e}")
                error_count += 1
                results.append({
                    'pc_name': device.get('pc_name', 'Unknown'),
                    'device_sync': 'error',
                    'latency_sync': 'error',
                    'error': str(e)
                })
        
        return jsonify({
            'status': 'success',
            'summary': {
                'total_devices': len(all_devices),
                'successful_syncs': success_count,
                'failed_syncs': error_count
            },
            'results': results,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en sync_to_appsheet: {e}")
        return jsonify({
            'status': 'error', 
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/appsheet/history/<pc_name>')
def get_appsheet_history(pc_name):
    """Obtener historial de un dispositivo desde AppSheet"""
    try:
        if not src.appsheet:
            return jsonify({
                "status": "error",
                "message": "AppSheet no está configurado"
            }), 400
        
        limit = request.args.get('limit', 50, type=int)
        days = request.args.get('days', 7, type=int)
        
        history = src.appsheet.get_device_history(pc_name, limit=limit, days=days)
        
        return jsonify({
            'status': 'success',
            'pc_name': pc_name,
            'history': history,
            'count': len(history),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo historial para {pc_name}: {e}")
        return jsonify({
            'status': 'error', 
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/appsheet/alerts')
def get_appsheet_alerts():
    """Obtener alertas recientes desde AppSheet"""
    try:
        if not src.appsheet:
            return jsonify({
                "status": "error",
                "message": "AppSheet no está configurado"
            }), 400
        
        limit = request.args.get('limit', 20, type=int)
        unresolved_only = request.args.get('unresolved', 'true').lower() == 'true'
        
        alerts = src.appsheet.get_recent_alerts(limit=limit, unresolved_only=unresolved_only)
        
        return jsonify({
            'status': 'success',
            'alerts': alerts,
            'count': len(alerts),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo alertas: {e}")
        return jsonify({
            'status': 'error', 
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/appsheet/stats')
def get_appsheet_stats():
    """Obtener estadísticas desde AppSheet"""
    try:
        if not src.appsheet:
            return jsonify({
                "status": "error",
                "message": "AppSheet no está configurado"
            }), 400
        
        days = request.args.get('days', 1, type=int)
        
        stats = src.appsheet.get_system_stats(days=days)
        
        return jsonify({
            'status': 'success',
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        # Devolver estadísticas básicas si AppSheet falla
        return jsonify({
            'status': 'success',
            'stats': {
                'avg_latency': 0,
                'avg_cpu': 0,
                'total_records': 0,
                'uptime_percent': 0,
                'active_alerts': 0
            },
            'timestamp': datetime.now().isoformat(),
            'note': 'Estadísticas por defecto (AppSheet no disponible)'
        })

@app.route('/api/appsheet/status')
def get_appsheet_status():
    """Verificar estado de conexión con AppSheet"""
    try:
        if not src.appsheet:
            return jsonify({
                "status": "disabled",
                "message": "AppSheet no está configurado",
                "available": False
            })
        
        is_available = src.appsheet.is_available()
        last_sync = src.appsheet.get_last_sync_time()
        
        return jsonify({
            "status": "enabled",
            "available": is_available,
            "last_sync": last_sync.isoformat() if last_sync else None,
            "message": "AppSheet disponible" if is_available else "AppSheet no responde"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "available": False,
            "message": str(e)
        })

# 8. MIDDLEWARE PARA REGISTRO DE ACCESOS
@app.before_request
def log_request():
    """Registrar todas las solicitudes HTTP"""
    if request.path not in ['/health', '/static']:
        logger.info(f"{request.method} {request.path} - {request.remote_addr}")

# 9. MANEJADOR DE ERRORES
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        "status": "error",
        "message": "Recurso no encontrado",
        "path": request.path
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Error interno del servidor: {error}")
    return jsonify({
        "status": "error",
        "message": "Error interno del servidor",
        "error_id": datetime.now().timestamp()
    }), 500

# 10. INICIO DEL SERVIDOR
if __name__ == '__main__':
    # Mostrar información de configuración
    logger.info("=" * 50)
    logger.info("🚀 INICIANDO ARGOS ENTERPRISE")
    logger.info("=" * 50)
    logger.info(f"📁 Directorio base: {base_dir}")
    logger.info(f"📁 Plantillas: {template_dir}")
    logger.info(f"📁 Estáticos: {static_dir}")
    logger.info(f"💾 Base de datos: {db_path}")
    logger.info(f"☁️ AppSheet: {'HABILITADO' if src.appsheet else 'DESHABILITADO'}")
    logger.info("=" * 50)
    
    # Render asigna el puerto en la variable de entorno PORT.
    # Si esa variable no existe (local), usamos 8000 como solicitaste.
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
