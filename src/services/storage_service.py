import json
import os
import threading
from datetime import datetime

class StorageService:
    def __init__(self, file_path, alert_service=None):
        self.file_path = file_path
        self.alert_service = alert_service
        self.lock = threading.Lock()
        
        # Diccionario en memoria para saber a quién ya alertamos
        # Estructura: {'PC_NAME': {'status': 'offline', 'email_sent': True}}
        self.alert_states = {} 
        
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({}, f)

    def get_all_devices(self):
        """Devuelve todos los datos tal cual están en el JSON."""
        with self.lock:
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

    def save_device_report(self, data):
        """
        Guarda el reporte de una NUC.
        Maneja la lógica de reconexión (Offline -> Online).
        """
        pc_name = data.get('pc_name')
        if not pc_name: return

        with self.lock:
            # 1. Cargar datos actuales
            try:
                with open(self.file_path, 'r') as f:
                    store = json.load(f)
            except:
                store = {}

            # 2. Verificar RECONEXIÓN
            # Si estaba marcado como offline y alertado, y ahora reporta:
            prev_state = self.alert_states.get(pc_name, {})
            if prev_state.get('status') == 'offline':
                print(f"✅ RECONEXIÓN DETECTADA: {pc_name}")
                if self.alert_service:
                    self.alert_service.send_online_alert(pc_name, data)
                
                # Actualizar estado interno a online
                self.alert_states[pc_name] = {'status': 'online', 'email_sent': False}

            # 3. Guardar datos nuevos en disco
            store[pc_name] = data
            with open(self.file_path, 'w') as f:
                json.dump(store, f, indent=4)
