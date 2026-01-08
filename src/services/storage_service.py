import json
import os
import threading
from src.models.device import Device

class StorageService:
    def __init__(self, data_file_path, alert_service=None):
        self.data_file = data_file_path
        self.alert_service = alert_service
        self.devices = {}
        self.lock = threading.RLock()
        self.load_from_disk()

    def load_from_disk(self):
        if not os.path.exists(self.data_file): return
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                with self.lock:
                    for pc_name, dev_data in data.items():
                        dev_data.pop('pc_name', None)
                        self.devices[pc_name] = Device(pc_name, **dev_data)
        except Exception: pass

    def update_device(self, pc_name, payload):
        with self.lock:
            if pc_name not in self.devices:
                self.devices[pc_name] = Device(pc_name, unit=payload.get('unit', 'Sin Asignar'))
            device = self.devices[pc_name]
            prev_status = device.status
            device.update_telemetry(payload)
            if self.alert_service:
                self.alert_service.check_and_alert(device, prev_status)
            self._save()

    def _save(self):
        data = {k: v.to_dict() for k, v in self.devices.items()}
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def get_all_devices(self):
        with self.lock: return [v.to_dict() for v in self.devices.values()]

    # --- Lógica de Inventario ---
    def save_inventory_log(self, record):
        with self.lock:
            path = os.path.join(os.path.dirname(self.data_file), 'inventory_logs.json')
            logs = self.get_inventory_logs()
            logs.append(record)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2)

    def delete_inventory_log(self, timestamp):
        with self.lock:
            path = os.path.join(os.path.dirname(self.data_file), 'inventory_logs.json')
            logs = self.get_inventory_logs()
            new_logs = [l for l in logs if l.get('timestamp') != timestamp]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(new_logs, f, indent=2)

    def get_inventory_logs(self):
        path = os.path.join(os.path.dirname(self.data_file), 'inventory_logs.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []