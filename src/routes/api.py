from flask import Blueprint, request, jsonify
import logging
from datetime import datetime
import src  # Acceso a las variables globales: src.monitor, src.supabase

logger = logging.getLogger(__name__)

bp = Blueprint('api', __name__, url_prefix='/api')

# ==============================================================================
# 1. REPORTES DE AGENTES (Ingesta de Datos: Latencia, Sensores, Estado)
# ==============================================================================
@bp.route('/report', methods=['POST'])
def receive_report():
    """
    Recibe el JSON enviado por el agente Python en la PC.
    Contiene: latencia, packet_loss, cpu, ram, extended_sensors, etc.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data"}), 400

        # Validación de Identidad
        device_id = data.get('mac_address') or data.get('pc_name')
        if not device_id:
            return jsonify({"status": "error", "message": "Missing ID"}), 400

        # A. RUTA RÁPIDA: MONITOR EN MEMORIA (Prioridad)
        # El monitor se encarga de:
        # 1. Guardar en RAM para el dashboard en vivo.
        # 2. Procesar la latencia (1 hora o picos).
        # 3. Guardar sensores y contadores en Supabase.
        if src.monitor:
            src.monitor.ingest_data(data)
            return jsonify({"status": "success", "handler": "monitor"}), 200
        
        # B. RUTA DE RESPALDO: ESCRITURA DIRECTA EN DB
        # Si el monitor falló o se está reiniciando, guardamos directo para no perder datos.
        elif src.supabase and hasattr(src.supabase, 'upsert_device_status'):
            logger.warning("⚠️ Monitor no disponible, guardando directo en DB (Fallback)")
            
            src.supabase.upsert_device_status({
                "device_id": device_id,
                "pc_name": data.get('pc_name'),
                "status": data.get('status', 'online'),
                "ip_address": data.get('ip_address'),
                "cpu_load": data.get('cpu_load_percent'),
                "ram_usage": data.get('ram_percent'),
                "sensors": data.get('extended_sensors'), # Guardamos sensores
                "last_seen": datetime.utcnow().isoformat()
            })
            
            # Intentar guardar métrica de latencia si existe
            if 'latency_ms' in data:
                src.supabase.buffer_metric(
                    device_id=device_id,
                    latency=data.get('latency_ms'),
                    packet_loss=data.get('packet_loss', 0)
                )
                
            return jsonify({"status": "success", "handler": "direct_db"}), 200

        else:
            return jsonify({"status": "error", "message": "System unavailable"}), 503

    except Exception as e:
        logger.error(f"❌ Error procesando reporte: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ==============================================================================
# 2. DATOS PARA EL DASHBOARD (Lectura)
# ==============================================================================
@bp.route('/data', methods=['GET'])
def get_all_data():
    """
    Devuelve el estado actual de todos los dispositivos ACTIVOS.
    """
    try:
        # OPCIÓN A: Leer de RAM (Monitor) - Es lo más rápido y fresco
        if src.monitor:
            # Filtramos para no enviar equipos dados de baja
            active_devices = {
                k: v for k, v in src.monitor.devices_state.items() 
                if v.get('status') != 'inactive'
            }
            return jsonify(active_devices)

        # OPCIÓN B: Leer de Base de Datos (Supabase) - Si el monitor no está listo
        elif src.supabase and hasattr(src.supabase, 'client'):
            # Traemos solo los que NO están inactivos
            response = src.supabase.client.table('devices').select('*').neq('status', 'inactive').execute()
            
            devices_map = {}
            for item in response.data:
                # MAPEO CRÍTICO: La DB tiene 'sensors', el Frontend espera 'extended_sensors'
                item['extended_sensors'] = item.get('sensors')
                item['ram_percent'] = item.get('ram_usage') # DB: ram_usage, Front: ram_percent
                
                devices_map[item['pc_name']] = item
                
            return jsonify(devices_map)
            
        return jsonify({})
    except Exception as e:
        logger.error(f"Error getting data: {e}")
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# 3. BITÁCORA E HISTORIAL (Logs y Automatización)
# ==============================================================================
@bp.route('/history/all', methods=['GET'])
def get_history():
    """Obtiene los logs de mantenimiento para la tabla."""
    try:
        if src.supabase and hasattr(src.supabase, 'client'):
            # Traemos últimos 200 logs
            response = src.supabase.client.table('logs')\
                .select('*')\
                .order('timestamp', desc=True)\
                .limit(200)\
                .execute()
            
            # Adaptamos nombres de campos para el Frontend
            history = []
            for item in response.data:
                history.append({
                    "device_id": item.get('device_id'),
                    "pc_name": item.get('pc_name'),
                    "action": item.get('action'),
                    "what": item.get('what'),
                    "desc": item.get('description'),
                    "req": item.get('requested_by'),
                    "exec": item.get('executed_by'),
                    # Convertimos a string "true"/"false" para facilitar JS
                    "solved": str(item.get('is_solved')).lower(), 
                    "timestamp": item.get('timestamp')
                })
            return jsonify(history)
        return jsonify([])
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return jsonify([])


@bp.route('/history/add', methods=['POST'])
def add_history():
    """
    Guarda un log y ejecuta acciones automáticas (como Dar de Baja).
    """
    try:
        data = request.get_json()
        if not src.supabase:
            return jsonify({"status": "error", "message": "Database offline"}), 503

        pc_name = data.get('pc_name')
        action = data.get('action', '')

        # 1. Guardar en Bitácora (Logs)
        payload = {
            "device_id": pc_name,
            "pc_name": pc_name,
            "action": action,
            "what": data.get('what'),
            "description": data.get('desc'),
            "requested_by": data.get('req'),
            "executed_by": data.get('exec'),
            "is_solved": data.get('solved') == 'true',
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Insertamos en la tabla logs
        src.supabase.client.table('logs').insert(payload).execute()

        # 2. LÓGICA DE BAJA AUTOMÁTICA
        # Si la acción sugiere que el equipo ya no existe, lo desactivamos del monitor
        action_lower = action.lower()
        if 'baja' in action_lower or 'retiro' in action_lower or 'descontinuado' in action_lower:
            logger.info(f"📉 Procesando BAJA automática para {pc_name}")
            
            # A. Actualizar tabla devices en Supabase (status = inactive)
            # Esto hace que deje de salir en el dashboard si se recarga desde la DB
            src.supabase.client.table('devices').update({
                "status": "inactive",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("pc_name", pc_name).execute()
            
            # B. Actualizar memoria del monitor en vivo
            # Esto hace que desaparezca inmediatamente del dashboard sin recargar
            if src.monitor and pc_name in src.monitor.devices_state:
                # Opción 1: Marcarlo inactivo
                src.monitor.devices_state[pc_name]['status'] = 'inactive'
                # Opción 2 (Más agresiva): Borrarlo de la RAM
                # del src.monitor.devices_state[pc_name]

        return jsonify({"status": "success", "message": "Log guardado y procesado"})

    except Exception as e:
        logger.error(f"Error saving log: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
