# ... (Todo el código anterior en src/routes/api.py se mantiene igual) ...

# ==========================================
# NUEVAS RUTAS PARA EL DASHBOARD DE APPSHEET
# ==========================================

@bp.route('/appsheet/status', methods=['GET'])
def appsheet_status():
    """
    Ruta que consume el Dashboard para ver si AppSheet está conectado.
    Resuelve el error 404 en /api/appsheet/status
    """
    try:
        # Verificar si el servicio está inicializado
        if hasattr(src, 'appsheet') and src.appsheet:
            # Obtenemos la info detallada del servicio
            status_info = src.appsheet.get_status_info()
            
            # Agregamos info del Monitor (si está corriendo el hilo)
            if hasattr(src, 'monitor') and src.monitor:
                status_info['monitor_running'] = src.monitor.running
            else:
                status_info['monitor_running'] = False
                
            return jsonify(status_info), 200
        else:
            return jsonify({
                "status": "disabled",
                "message": "Servicio AppSheet no inicializado en el backend",
                "available": False
            }), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/appsheet/sync', methods=['POST'])
def appsheet_sync_trigger():
    """
    Ruta para el botón 'Sincronizar Ahora'.
    """
    try:
        if hasattr(src, 'monitor') and src.monitor:
            # Forzamos la sincronización en el hilo de fondo
            src.monitor.force_manual_sync()
            return jsonify({
                "success": True, 
                "message": "Sincronización iniciada correctamente"
            }), 200
        else:
            return jsonify({
                "success": False, 
                "message": "El monitor de AppSheet no está activo"
            }), 503
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/appsheet/config', methods=['POST'])
def appsheet_config():
    """
    (Opcional) Si tu dashboard tiene un formulario para guardar API KEY.
    """
    # Por seguridad, por ahora solo retornamos que se debe configurar por variable de entorno
    return jsonify({
        "success": False,
        "message": "Por seguridad, configure APPSHEET_API_KEY en las variables de entorno del servidor (Render/ .env)"
    }), 403
