import os
import logging
from datetime import datetime
from flask import Flask, jsonify, request, render_template, send_from_directory
import traceback

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuración
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-123')
app.config['ENV'] = os.getenv('FLASK_ENV', 'production')

# Importar servicios DESPUÉS de crear la app
from src.services.appsheet_service import AppSheetService

# Variable global para el servicio (opcional)
appsheet_service = None

@app.before_first_request
def initialize_services():
    """Inicializar servicios al arrancar"""
    global appsheet_service
    logger.info("🚀 Inicializando servicios...")
    
    try:
        # AppSheet Service
        appsheet_service = AppSheetService()
        app.config['appsheet_service'] = appsheet_service
        
        status = appsheet_service.get_status_info()
        logger.info(f"📊 AppSheet Status: {status['connection_status']}")
        
        if appsheet_service.enabled:
            logger.info("✅ AppSheet Service inicializado y CONECTADO")
        else:
            logger.warning("⚠️ AppSheet Service en modo DESCONECTADO")
            
    except Exception as e:
        logger.error(f"🔥 Error inicializando servicios: {e}")
        appsheet_service = None

# ==================== RUTAS BÁSICAS ====================

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    """Favicon para evitar error 404"""
    try:
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )
    except:
        # Si no hay favicon, devolver vacío
        return '', 204

# ==================== RUTAS DE APPSHEET ====================

@app.route('/api/appsheet/status', methods=['GET'])
def get_appsheet_status():
    """Endpoint para verificar estado de AppSheet"""
    try:
        if appsheet_service:
            status = appsheet_service.get_status_info()
        else:
            # Crear servicio temporal si no está inicializado
            service = AppSheetService()
            status = service.get_status_info()
        
        return jsonify({
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "status": status
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/appsheet/test', methods=['POST', 'GET'])
def test_appsheet():
    """Endpoint para probar conexión con AppSheet"""
    try:
        # Crear servicio si no está inicializado
        service = appsheet_service or AppSheetService()
        
        if request.method == 'POST':
            # Datos del request
            test_data = request.json or {
                "pc_name": "TEST_PC_" + datetime.now().strftime('%H%M%S'),
                "action": "connection_test",
                "desc": "Prueba de conexión desde API",
                "unit": "Testing"
            }
            
            # Probar escritura
            success = service.add_history_entry(test_data)
            
            # Probar lectura
            history = service.get_full_history(limit=3)
            
            return jsonify({
                "success": success,
                "test_data": test_data,
                "recent_history": history,
                "service_status": service.get_status_info()
            })
        else:
            # GET request - solo mostrar estado
            return jsonify({
                "service_status": service.get_status_info(),
                "instructions": "Envía un POST con datos para probar escritura"
            })
            
    except Exception as e:
        logger.error(f"Error en test_appsheet: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc() if app.debug else None
        }), 500

@app.route('/api/appsheet/debug', methods=['GET'])
def debug_appsheet():
    """Página de debug para AppSheet"""
    try:
        service = AppSheetService()  # Nueva instancia para debug
        
        # Obtener información básica
        status = service.get_status_info()
        
        # Información de entorno (sin exponer credenciales completas)
        env_info = {
            "APPSHEET_ENABLED": os.getenv('APPSHEET_ENABLED', 'Not set'),
            "APPSHEET_APP_ID": service.app_id[:8] + "..." if service.app_id else "None",
            "APPSHEET_API_KEY": "Set" if service.api_key else "Not set",
            "API_KEY_LENGTH": len(service.api_key) if service.api_key else 0
        }
        
        # Probar cada tabla
        table_tests = []
        tables_to_test = ["devices", "device_history", "latency_history", "alerts"]
        
        for table in tables_to_test:
            try:
                if service.enabled and service.app_id and service.api_key:
                    # Probar con el método del servicio
                    test_result = service._make_safe_request(
                        table, 
                        "Find", 
                        properties={"Locale": "es-MX", "Top": 1}
                    )
                    
                    exists = test_result is not None
                    table_tests.append({
                        "table": table,
                        "exists": exists,
                        "tested_with": "service_method"
                    })
                else:
                    table_tests.append({
                        "table": table,
                        "error": "Service not enabled or missing credentials",
                        "exists": False
                    })
                    
            except Exception as e:
                table_tests.append({
                    "table": table,
                    "error": str(e),
                    "exists": False
                })
        
        return jsonify({
            "debug_timestamp": datetime.now().isoformat(),
            "service_status": status,
            "environment": env_info,
            "table_tests": table_tests,
            "available_methods": [
                "get_status_info", "add_history_entry", "get_full_history",
                "get_or_create_device", "add_latency_to_history", "add_alert"
            ]
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

# ==================== RUTAS DE SISTEMA ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "ARGOS Server",
        "version": "1.0.0"
    })

@app.route('/api/info', methods=['GET'])
def system_info():
    """Información del sistema"""
    return jsonify({
        "app_name": "ARGOS Monitoring System",
        "environment": app.config['ENV'],
        "debug_mode": app.debug,
        "services": {
            "appsheet": appsheet_service.get_status_info() if appsheet_service else "Not initialized"
        }
    })

# ==================== MANEJO DE ERRORES ====================

@app.errorhandler(404)
def not_found(error):
    """Manejo de errores 404"""
    return jsonify({
        "error": "Endpoint not found",
        "path": request.path,
        "timestamp": datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Manejo de errores 500"""
    logger.error(f"500 Error: {error}\n{traceback.format_exc()}")
    return jsonify({
        "error": "Internal server error",
        "timestamp": datetime.now().isoformat()
    }), 500

# ==================== INICIALIZACIÓN ====================

if __name__ == '__main__':
    # Inicializar servicios inmediatamente
    try:
        appsheet_service = AppSheetService()
        logger.info(f"✅ AppSheet Service inicializado: {appsheet_service.get_status_info()}")
    except Exception as e:
        logger.error(f"⚠️ Error inicializando AppSheet Service: {e}")
        appsheet_service = None
    
    # Configurar puerto
    port = int(os.getenv('PORT', 5000))
    
    # Ejecutar app
    logger.info(f"🚀 Iniciando ARGOS Server en puerto {port}")
    app.run(
        host='0.0.0.0',
        port=port,
        debug=(app.config['ENV'] == 'development')
    )
