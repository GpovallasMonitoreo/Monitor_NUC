import os
from flask import request, jsonify, render_template
from src import create_app

# 1. Creamos la app base (trayendo configuración de src)
app = create_app()

# --- INICIO LÓGICA DE MONITOREO (Argos) ---
# Esta sección inyecta las rutas necesarias para el monitor en tiempo real
# en la aplicación que acabamos de importar.

# Memoria Volátil (Base de datos en RAM)
live_inventory = {}

# Ruta A: Recibir reporte de los agentes (Python scripts en las NUCs)
@app.route('/api/report', methods=['POST'])
def receive_report():
    try:
        data = request.json
        # Usamos el nombre del equipo como clave única
        live_inventory[data['pc_name']] = data
        return jsonify({"status": "received", "pc": data['pc_name']}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Ruta B: Entregar datos al Frontend (JavaScript del navegador)
@app.route('/api/live-data', methods=['GET'])
def get_live_data():
    # Convertimos el diccionario a lista para que JS lo pueda iterar
    return jsonify(list(live_inventory.values()))

# Ruta C: Asegurar que la ruta /monitor renderice el HTML correcto
# (Si ya tienes esta ruta en src/routes.py o similar, puedes borrar este bloque,
# pero dejarlo aquí asegura que funcione la demo)
@app.route('/monitor_live')
def monitor_live():
    return render_template('monitor.html')

# --- FIN LÓGICA DE MONITOREO ---

if __name__ == '__main__':
    print("\n--- ARGOS MONITOR INICIADO ---")
    print("Rutas de API activas:")
    print(" -> POST /api/report (Para recibir datos)")
    print(" -> GET  /api/live-data (Para el dashboard)")
    print("--------------------------------\n")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)