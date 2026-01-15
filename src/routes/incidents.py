from flask import Blueprint, request, jsonify
import src # Acceso a supabase y monitor

bp = Blueprint('incidents', __name__, url_prefix='/api/incidents')

# 1. REPORTAR FALLA MANUAL (Vandalismo, Fibra, etc.)
@bp.route('/report', methods=['POST'])
def report_incident():
    try:
        data = request.get_json()
        payload = {
            "device_id": data.get('device_id'),
            "issue_type": data.get('type'), # vandalismo, fibra, energia...
            "description": data.get('description'),
            "reported_by": "Admin",
            "incident_date": "now()"
        }
        src.supabase.client.table('incidents').insert(payload).execute()
        return jsonify({"status": "success", "msg": "Incidente registrado"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. CALCULAR SEMÁFORO DE RIESGO (Automático + Manual)
@bp.route('/risk-map', methods=['GET'])
def get_risk_map():
    try:
        # A) Obtener contadores automáticos de los dispositivos
        response_devs = src.supabase.client.table('devices').select('pc_name, disconnect_count, lat, lng').execute()
        devices = response_devs.data
        
        # B) Obtener incidentes manuales
        response_incs = src.supabase.client.table('incidents').select('*').execute()
        incidents = response_incs.data
        
        risk_map = []

        for dev in devices:
            pc_name = dev.get('pc_name')
            # 1. Sumar desconexiones automáticas
            auto_fails = dev.get('disconnect_count', 0)
            
            # 2. Sumar reportes manuales para este equipo
            manual_fails = len([i for i in incidents if i['device_id'] == pc_name])
            
            # 3. Total de problemas
            total_issues = auto_fails + manual_fails
            
            # 4. Determinar Color (Semáforo)
            status = "stable" # Verde
            if total_issues >= 10: status = "critical" # Rojo
            elif total_issues >= 3: status = "unstable" # Amarillo
            
            # Solo enviamos si tiene ubicación
            if dev.get('lat'):
                risk_map.append({
                    "device_id": pc_name,
                    "lat": dev.get('lat'),
                    "lng": dev.get('lng'),
                    "auto_disconnects": auto_fails,
                    "manual_reports": manual_fails,
                    "total": total_issues,
                    "risk_level": status
                })
            
        return jsonify(risk_map)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
