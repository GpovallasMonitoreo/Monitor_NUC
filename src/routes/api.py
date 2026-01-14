from flask import Blueprint, request, jsonify
import logging
from datetime import datetime
import src  # Acceso a las variables globales: src.monitor, src.supabase

logger = logging.getLogger(__name__)

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/report', methods=['POST'])
def receive_report():
    """
    Endpoint principal que recibe datos de los agentes instalados en las PC.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data"}), 400

        # Validación básica de identidad
        device_id = data.get('mac_address') or data.get('pc_name')
        if not device_id:
            return jsonify({"status": "error", "message": "Missing ID"}), 400

        # 1. Intentar pasar los datos al MONITOR (La vía preferida)
        # El monitor se encarga de analizar alertas y hacer buffer de latencia
        if src.monitor:
            src.monitor.ingest_data(data)
            return jsonify({"status": "success", "handler": "monitor"}), 200
        
        # 2. Fallback: Si el monitor falló, intentamos guardar directo en Supabase
        # Esto asegura que no se pierdan datos aunque el monitor esté reiniciándose
        elif src.supabase and hasattr(src.supabase, 'upsert_device_status'):
            logger.warning("⚠️ Monitor no disponible, guardando directo en DB")
            
            # Guardar estado
            src.supabase.upsert_device_status({
                "device_id": device_id,
                "pc_name": data.get('pc_name'),
                "status": data.get('status', 'online'),
                "ip_address": data.get('ip_address'),
                "last_seen": datetime.utcnow().isoformat()
            })
            
            # Guardar métrica si existe
            if 'latency_ms' in data:
                src.supabase.buffer_metric(
                    device_id=device_id, 
                    latency=data.get('latency_ms'),
                    packet_loss=data.get('packet_loss', 0)
                )
                
            return jsonify({"status": "success", "handler": "direct_db"}), 200

        else:
            logger.error("❌ Sistema crítico: Ni Monitor ni Supabase están disponibles")
            return jsonify({"status": "error", "message": "System unavailable"}), 503

    except Exception as e:
        logger.error(f"❌ Error procesando reporte: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/data', methods=['GET'])
def get_all_data():
    """Endpoint para ver datos crudos en el navegador (Depuración)"""
    try:
        # Obtenemos datos de la memoria del monitor si es posible
        if src.monitor:
            devices = src.monitor.devices_state
            return jsonify(devices)
        else:
            return jsonify({"status": "Monitor not running", "data": {}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
