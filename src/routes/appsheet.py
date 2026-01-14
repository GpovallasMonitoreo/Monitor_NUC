# src/routes/appsheet.py
from flask import Blueprint, jsonify, request
from datetime import datetime
import src  # Importamos el paquete para acceder a las variables globales (src.appsheet, src.storage)

bp = Blueprint('appsheet', __name__, url_prefix='/api/appsheet')

@bp.route('/status', methods=['GET'])
def get_status():
    """Endpoint para verificar estado de AppSheet"""
    try:
        service = src.appsheet
        # Usamos el método del servicio, sea Stub o Real
        status = service.get_status_info()
        
        return jsonify({
            "success": True,
            "available": service.enabled,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/sync', methods=['POST'])
def manual_sync():
    """Sincronización manual"""
    if not src.appsheet.enabled:
        return jsonify({"success": False, "error": "AppSheet deshabilitado"}), 400

    results = {"synced": 0, "errors": 0}
    
    # Ejemplo de uso del StorageService global
    local_data = src.storage.get_all_devices() if src.storage else {}

    for dev_id, data in local_data.items():
        success, _, _ = src.appsheet.get_or_create_device(data)
        if success:
            results["synced"] += 1
        else:
            results["errors"] += 1

    return jsonify({
        "success": True, 
        "results": results,
        "timestamp": datetime.now().isoformat()
    })
