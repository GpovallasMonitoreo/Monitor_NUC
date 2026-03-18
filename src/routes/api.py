from flask import Blueprint, request, jsonify
import logging
from datetime import datetime
import time  # NUEVO: Necesario para el reloj del servidor
import src  

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

        # --- NUEVO: RELOJ DEL SERVIDOR Y ESTADO ---
        # Le inyectamos la hora exacta del servidor para no depender del reloj de la NUC
        data['server_timestamp'] = time.time()
        data['status'] = 'online'

        # --- NUEVO: AUTO-REGISTRO EN SUPABASE ---
        # Forzamos a la base de datos a crear el equipo si es nuevo, 
        # y guardamos sus datos de GPS e ISP.
        if src.supabase and hasattr(src.supabase, 'client'):
            try:
                device_payload = {
                    "device_id": device_id,
                    "pc_name": data.get('pc_name'),
                    "unit": data.get('unit', 'CENTRO'),
                    "status": "online",
                    "ip_address": data.get('ip'),
                    "cpu_load": data.get('cpu_load_percent'),
                    "ram_usage": data.get('ram_percent'),
                    "sensors": data.get('extended_sensors'),
                    "last_seen": datetime.utcnow().isoformat()
                }
                # Añadimos los campos nuevos de geo si vienen en el paquete
                if 'public_ip' in data: device_payload['public_ip'] = data['public_ip']
                if 'lat' in data: device_payload['lat'] = data['lat']
                if 'lng' in data: device_payload['lng'] = data['lng']
                if 'city' in data: device_payload['city'] = data['city']
                if 'isp' in data: device_payload['isp'] = data['isp']

                # Upsert inserta si no existe, o actualiza si ya existe
                src.supabase.client.table('devices').upsert(device_payload).execute()
            except Exception as e:
                logger.error(f"⚠️ Error en auto-registro de DB: {e}")


        # A. RUTA RÁPIDA: MONITOR EN MEMORIA (Prioridad)
        if src.monitor:
            src.monitor.ingest_data(data)
            return jsonify({"status": "success", "handler": "monitor"}), 200
        
        # B. RUTA DE RESPALDO: ESCRITURA DIRECTA EN DB
        elif src.supabase and hasattr(src.supabase, 'upsert_device_status'):
            logger.warning("⚠️ Monitor no disponible, guardando directo en DB (Fallback)")
            
            src.supabase.upsert_device_status({
                "device_id": device_id,
                "pc_name": data.get('pc_name'),
                "status": "online",
                "ip_address": data.get('ip'),
                "cpu_load": data.get('cpu_load_percent'),
                "ram_usage": data.get('ram_percent'),
                "sensors": data.get('extended_sensors'), 
                "last_seen": datetime.utcnow().isoformat()
            })
            
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
        current_time = time.time() # NUEVO: Hora actual del servidor

        # OPCIÓN A: Leer de RAM (Monitor) - Es lo más rápido y fresco
        if src.monitor:
            active_devices = {}
            for k, v in src.monitor.devices_state.items():
                if v.get('status') == 'inactive':
                    continue
                
                # --- NUEVO: EVALUACIÓN ESTRICTA DE DESCONEXIÓN ---
                # Si pasaron más de 90 segundos desde el último paquete, lo matamos
                last_seen = v.get('server_timestamp')
                if last_seen and (current_time - last_seen > 90):
                    v['status'] = 'offline'
                    
                active_devices[k] = v
                
            return jsonify(active_devices)

        # OPCIÓN B: Leer de Base de Datos (Supabase) - Si el monitor no está listo
        elif src.supabase and hasattr(src.supabase, 'client'):
            response = src.supabase.client.table('devices').select('*').neq('status', 'inactive').execute()
            
            devices_map = {}
            for item in response.data:
                item['extended_sensors'] = item.get('sensors')
                item['ram_percent'] = item.get('ram_usage') 
                
                # --- NUEVO: Evaluar desconexión también en base de datos ---
                last_seen_iso = item.get('last_seen')
                if last_seen_iso:
                    try:
                        last_seen_dt = datetime.fromisoformat(last_seen_iso.replace('Z', '+00:00')).replace(tzinfo=None)
                        if (datetime.utcnow() - last_seen_dt).total_seconds() > 90:
                            item['status'] = 'offline'
                    except:
                        pass
                
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
            response = src.supabase.client.table('logs')\
                .select('*')\
                .order('timestamp', desc=True)\
                .limit(200)\
                .execute()
            
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
        
        src.supabase.client.table('logs').insert(payload).execute()

        action_lower = action.lower()
        if 'baja' in action_lower or 'retiro' in action_lower or 'descontinuado' in action_lower:
            logger.info(f"📉 Procesando BAJA automática para {pc_name}")
            
            src.supabase.client.table('devices').update({
                "status": "inactive",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("pc_name", pc_name).execute()
            
            if src.monitor and pc_name in src.monitor.devices_state:
                src.monitor.devices_state[pc_name]['status'] = 'inactive'

        return jsonify({"status": "success", "message": "Log guardado y procesado"})

    except Exception as e:
        logger.error(f"Error saving log: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
