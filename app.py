from flask import Flask, render_template, jsonify, request
import datetime

app = Flask(__name__)

# MEMORIA VOLÁTIL (Simulando una Base de Datos)
# Aquí guardaremos el último estado reportado por cada PC.
# Clave: nombre_pc, Valor: datos
infrastructure_state = {}

@app.route('/')
def home():
    return render_template('base.html') # O tu dashboard inicial

@app.route('/monitor')
def monitor():
    return render_template('monitor.html')

# --- API ENDPOINTS ---

# 1. RECIBIR DATOS (Aquí dispara tu simulador)
@app.route('/api/report', methods=['POST'])
def receive_report():
    data = request.json
    pc_name = data.get('pc_name')
    
    # Agregamos timestamp de recepción
    data['last_seen'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Determinar estado basado en reglas simples
    cpu = data.get('cpu_load_percent', 0)
    temp = data['sensors'].get('cpu_temp', 0)
    
    if cpu > 90 or temp > 85:
        data['status'] = 'critical'
        data['status_text'] = 'CRITICO'
    elif cpu > 70 or temp > 70:
        data['status'] = 'warning'
        data['status_text'] = 'Atención'
    else:
        data['status'] = 'ok'
        data['status_text'] = 'Ok'
        
    # Guardar/Sobrescribir en memoria
    infrastructure_state[pc_name] = data
    
    return jsonify({"message": "Data received"}), 200

# 2. ENTREGAR DATOS AL FRONTEND (Aquí consulta el HTML)
@app.route('/api/monitor-data', methods=['GET'])
def get_monitor_data():
    equipos = list(infrastructure_state.values())
    total_equipos = len(equipos)
    
    if total_equipos == 0:
        return jsonify({
            "kpis": {"total": 0, "critical": 0, "avg_cpu": 0, "avg_temp": 0},
            "equipos": [],
            "charts": {"disk": [0,0,0], "top_cpu": []}
        })

    # Calcular KPIs en tiempo real
    alertas = sum(1 for e in equipos if e['status'] != 'ok')
    avg_cpu = sum(e['cpu_load_percent'] for e in equipos) / total_equipos
    avg_temp = sum(e['sensors']['cpu_temp'] for e in equipos) / total_equipos
    
    # Datos para gráfica de Discos (Simulados por ahora, o calculados si el simulador los envía)
    # Asumimos distribución simple basada en estado general para este ejemplo
    disk_opt = sum(1 for e in equipos if e['status'] == 'ok')
    disk_crit = sum(1 for e in equipos if e['status'] == 'warning')
    disk_super = sum(1 for e in equipos if e['status'] == 'critical')

    # Datos para Top Consumo (Ordenar por CPU y tomar top 5)
    sorted_by_cpu = sorted(equipos, key=lambda x: x['cpu_load_percent'], reverse=True)[:6]
    top_cpu_labels = [e['pc_name'] for e in sorted_by_cpu]
    top_cpu_values = [e['cpu_load_percent'] for e in sorted_by_cpu]

    return jsonify({
        "kpis": {
            "total": total_equipos,
            "critical": alertas,
            "avg_cpu": round(avg_cpu, 1),
            "avg_temp": round(avg_temp, 1)
        },
        "equipos": equipos, # Lista completa para la tabla
        "charts": {
            "disk": [disk_opt, disk_crit, disk_super],
            "top_cpu_labels": top_cpu_labels,
            "top_cpu_values": top_cpu_values
        }
    })

if __name__ == '__main__':
    # Ejecutar en modo debug y accesible
    app.run(debug=True, port=5000)