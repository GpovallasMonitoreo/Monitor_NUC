from flask import Blueprint, request, jsonify
import src # Acceso a supabase

bp = Blueprint('incidents', __name__, url_prefix='/api/incidents')

# 1. REPORTAR FALLA
@bp.route('/report', methods=['POST'])
def report_incident():
    try:
        data = request.get_json()
        payload = {
            "device_id": data.get('device_id'),
            "issue_type": data.get('type'), # desconexion, fibra, energia...
            "description": data.get('description'),
            "reported_by": "Admin", # O el usuario logueado
            "incident_date": "now()"
        }
        src.supabase.client.table('incidents').insert(payload).execute()
        
        # Opcional: Incrementar contador en tabla devices si se requiere persistencia rápida
        return jsonify({"status": "success", "msg": "Incidente registrado"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. OBTENER SEMÁFORO DE RIESGO (Para el Mapa)
@bp.route('/risk-map', methods=['GET'])
def get_risk_map():
    try:
        # Traemos todos los incidentes
        response = src.supabase.client.table('incidents').select('*').execute()
        incidents = response.data
        
        # Agrupamos por dispositivo para contar fallas
        risk_analysis = {}
        
        for inc in incidents:
            dev = inc['device_id']
            if dev not in risk_analysis:
                risk_analysis[dev] = {"count": 0, "types": []}
            
            risk_analysis[dev]["count"] += 1
            risk_analysis[dev]["types"].append(inc['issue_type'])

        # Determinamos color (Verde, Amarillo, Rojo)
        result = []
        for dev, data in risk_analysis.items():
            count = data["count"]
            status = "stable" # Verde
            
            if count >= 5: status = "critical" # Rojo
            elif count >= 2: status = "unstable" # Amarillo
            
            result.append({
                "device_id": dev,
                "total_incidents": count,
                "risk_level": status,
                "recent_issues": list(set(data["types"])) # Tipos únicos
            })
            
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
