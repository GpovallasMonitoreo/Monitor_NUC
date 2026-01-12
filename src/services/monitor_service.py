import time
import threading
import copy
import logging
from datetime import datetime
from typing import Dict, Any

# Configuración de umbrales
THRESHOLDS = {
    'cpu_spike': 40.0,       
    'temp_spike': 15.0,      
    'offline_timeout': 600,  # 10 minutos
    'periodic_sync': 900     # 15 minutos
}

logger = logging.getLogger(__name__)

class DeviceMonitorManager:
    """Gestor que orquesta el AppSheetService"""

    def __init__(self, appsheet_service):
        self.service = appsheet_service
        self.devices_state: Dict[str, Dict] = {} 
        self.running = False
        self.lock = threading.Lock()
        self.last_global_sync = datetime.now()
        self.monitor_thread = threading.Thread(target=self._background_loop, daemon=True)

    def start(self):
        if not self.running:
            self.running = True
            self.monitor_thread.start()
            logger.info("🚀 MonitorManager iniciado")

    def stop(self):
        self.running = False
        logger.info("🛑 MonitorManager detenido")

    def ingest_data(self, device_data: Dict[str, Any]):
        pc_name = device_data.get('pc_name')
        if not pc_name: return

        with self.lock:
            is_urgent = self._check_sudden_changes(pc_name, device_data)
            device_data['_last_seen_local'] = datetime.now()
            
            if pc_name not in self.devices_state:
                is_urgent = True 

            self.devices_state[pc_name] = device_data

        if is_urgent:
            logger.info(f"⚡ Cambio urgente en {pc_name}. Sincronizando.")
            self.service.sync_device_complete(device_data)
        else:
            # Siempre enviamos latencia para tener histórico
            self.service.add_latency_record(device_data)

    def force_manual_sync(self):
        logger.info("🔄 Sincronización manual solicitada")
        self._perform_bulk_sync()

    def _background_loop(self):
        while self.running:
            try:
                now = datetime.now()
                self._check_offline_devices(now)

                if (now - self.last_global_sync).total_seconds() >= THRESHOLDS['periodic_sync']:
                    logger.info("⏰ Sync programada 15 min")
                    self._perform_bulk_sync()
                    self.last_global_sync = now
                
                time.sleep(10)
            except Exception as e:
                logger.error(f"Error en monitor loop: {e}")
                time.sleep(30)

    def _check_sudden_changes(self, pc_name: str, new_data: Dict) -> bool:
        if pc_name not in self.devices_state: return False
        old_data = self.devices_state[pc_name]
        
        # Chequeo CPU
        try:
            cpu_diff = abs(float(new_data.get('cpu_load_percent', 0)) - float(old_data.get('cpu_load_percent', 0)))
            if cpu_diff > THRESHOLDS['cpu_spike']: return True
        except: pass

        # Chequeo Status
        if new_data.get('status') != old_data.get('status'): return True
        
        return False

    def _check_offline_devices(self, now: datetime):
        with self.lock:
            for pc_name, data in self.devices_state.items():
                last_seen = data.get('_last_seen_local')
                if not last_seen: continue
                
                if (now - last_seen).total_seconds() > THRESHOLDS['offline_timeout']:
                    if data.get('status') != 'offline':
                        logger.warning(f"💀 Watchdog: {pc_name} OFFLINE")
                        data['status'] = 'offline'
                        self.service.upsert_device(data)
                        self.service.add_alert(data, "watchdog_offline", "Dispositivo dejó de responder > 10m", "high")

    def _perform_bulk_sync(self):
        with self.lock:
            devices = copy.deepcopy(self.devices_state)
        for _, data in devices.items():
            self.service.upsert_device(data)
