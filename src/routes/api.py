import sys
import os
from flask import Blueprint, request, jsonify
from datetime import datetime

# --- BLOQUE DE CONFIGURACIÓN DE RUTAS ---
# Esto ayuda a Python a encontrar la carpeta 'src' cuando este archivo está dentro de 'routes'
# Básicamente le dice: "Busca módulos también en la carpeta anterior (la raíz del proyecto)"
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Ahora sí podemos importar 'src' sin miedo a "ModuleNotFoundError"
try:
    from src import storage, alerts
except ImportError as e:
    # Esto te ayudará a depurar si la estructura de carpetas no es la esperada
    print(f"⚠️ ARGOS ERROR CRÍTICO: No se pudo importar 'src'. Verifica tu estructura. Detalles: {e}")
    # En producción podrías querer detener la app o manejarlo diferente
    storage = None 
    alerts = None

# Definición del Blueprint
bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/data', methods=['GET'])
def get_data():
    """Obtiene todos los dispositivos almacenados."""
    try:
        return jsonify(storage.get_all_devices())
    except Exception as e:
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

@bp.route('/inventory/logs', methods=['GET'])
def get_logs():
    """Obtiene el historial de registros."""
    try:
        return jsonify(storage.get_inventory_logs())
    except Exception as e:
        return jsonify({"error": f"Error al obtener logs: {str(e)}"}), 500

@bp.route('/inventory/save', methods=['POST'])
def save_log():
    """Guarda un nuevo registro de inventario."""
    try:
        data = request.get_json()
        
        # Validación básica de seguridad
        if not data:
            return jsonify({"error": "No se recibieron datos JSON válidos"}), 400

        # Inyectar timestamp del servidor
        data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Guardar en base de datos/archivo
        storage.save_inventory_log(data)
        
        # Enviar alerta si el módulo está activo
        if alerts:
            try:
                alerts.send_inventory_report(data)
            except Exception as alert_error:
                print(f"⚠️ Alerta fallida, pero el dato se guardó: {alert_error}")

        return jsonify({"status": "success", "timestamp": data['timestamp']})

    except Exception as e:
        return jsonify({"error": f"Error procesando la solicitud: {str(e)}"}), 500

@bp.route('/inventory/delete', methods=['POST'])
def delete_log():
    """Elimina un registro basado en su timestamp."""
    try:
        data = request.get_json()
        
        if not data or 'timestamp' not in data:
            return jsonify({"error": "Falta el campo 'timestamp'"}), 400
            
        storage.delete_inventory_log(data.get('timestamp'))
        return jsonify({"status": "success"})
        
    except Exception as e:
        return jsonify({"error": f"Error al eliminar: {str(e)}"}), 500
