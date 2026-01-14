from flask import Blueprint, jsonify
from datetime import datetime
import src

bp = Blueprint('appsheet', __name__, url_prefix='/api/appsheet')

@bp.route('/status', methods=['GET'])
def get_status():
    """Adaptador de compatibilidad para Dashboard viejo"""
    try:
        # Verificamos Supabase en lugar de AppSheet
        is_online = False
        status_detail = "Offline"
        
        # Verificamos si src.supabase existe y NO es el Stub (mirando si tiene 'client')
        if src.supabase and hasattr(src.supabase, 'client'):
            is_online = True
            status_detail = "Connected (Supabase Backend)"
        
        return jsonify({
            "success": True,
            "available": is_online,
            "connected": is_online,
            "timestamp": datetime.now().isoformat(),
            "status": {"connection_status": status_detail}
        })
    except Exception as e:
        # Retornamos JSON de error pero con código 200 para no alarmar al dashboard
        return jsonify({"success": False, "error": str(e)}), 200
