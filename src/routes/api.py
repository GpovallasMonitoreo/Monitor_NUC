from flask import Blueprint, request, jsonify
from datetime import datetime
from src import storage, alerts 

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/data', methods=['GET'])
def get_data():
    return jsonify(storage.get_all_devices())

@bp.route('/inventory/logs', methods=['GET'])
def get_logs():
    return jsonify(storage.get_inventory_logs())

@bp.route('/inventory/save', methods=['POST'])
def save_log():
    data = request.get_json()
    data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    storage.save_inventory_log(data)
    if alerts:
        alerts.send_inventory_report(data)
    return jsonify({"status": "success"})

@bp.route('/inventory/delete', methods=['POST'])
def delete_log():
    data = request.get_json()
    storage.delete_inventory_log(data.get('timestamp'))
    return jsonify({"status": "success"})