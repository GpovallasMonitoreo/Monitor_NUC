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
    'periodic_sync': 900,    # 15 minutos
    'latency_record_interval': 3600  # 1 hora
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
            logger.info("🚀 MonitorManager iniciado (Throttle activado)")

    def stop(self):
        self.running = False
        logger.info("🛑 MonitorManager detenido")

    def ingest_data(self, device_data: Dict[str, Any]):
        pc_name = device_data.get('pc_name')
        if not pc_name: return

        with self.lock:
            old_data = self.devices_state.get(pc_name, {})
            
            # 1. Detectar urgencia
            is_urgent = self._check_sudden_changes(pc_name, device_data, old_data)
            
            # Actualizar timestamp local
            now = datetime.now()
            device_data['_last_seen_local'] = now
            
            if '_last_latency_sync' in old_data:
                device_data['_last_latency_sync'] = old_data['_last_latency_sync']
            
            self.devices_state[pc_name] = device_data

        # 2. Lógica de Envío
        if is_urgent:
            logger.info(f"⚡ Cambio urgente en {pc_name}. Sincronizando YA.")
            # CORRECCIÓN: Usamos upsert_device y add_latency_record manualmente para asegurar
            self.service.upsert_device(device_data)
            self.service.add_latency_record(device_data)
            
            with self.lock:
                self.devices_state[pc_name]['_last_latency_sync'] = now
        else:
            # 3. Lógica de Throttling (1 hora)
            last_sync = device_data.get('_last_latency_sync')
            should_record = False
            
            if not last_sync:
                should_record = True
            else:
                seconds_passed = (now - last_sync).total_seconds()
                if seconds_passed > THRESHOLDS['latency_record_interval']:
                    should_record = True
            
            if should_record:
                logger.info(f"⏳ Grabando historial programado para {pc_name}")
                self.service.add_latency_record(device_data)
                with self.lock:
                    self.devices_state[pc_name]['_last_latency_sync'] = now

    def force_manual_sync(self):
        logger.info("🔄 Sincronización manual solicitada")
        self._perform_bulk_sync(force_history=True)

    def _background_loop(self):
        while self.running:
            try:
                now = datetime.now()
                self._check_offline_devices(now)

                if (now - self.last_global_sync).total_seconds() >= THRESHOLDS['periodic_sync']:
                    logger.info("⏰ Sync Automática de Mantenimiento")
                    self._perform_bulk_sync(force_history=False)
                    self.last_global_sync = now
                
                time.sleep(10)
            except Exception as e:
                logger.error(f"Error en monitor loop: {e}")
                time.sleep(30)

    def _check_sudden_changes(self, pc_name: str, new_data: Dict, old_data: Dict) -> bool:
        if not old_data: return True 
        try:
            cpu_diff = abs(float(new_data.get('cpu_load_percent', 0)) - float(old_data.get('cpu_load_percent', 0)))
            if cpu_diff > THRESHOLDS['cpu_spike']: return True
        except: pass
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

    def _perform_bulk_sync(self, force_history: bool = False):
        with self.lock:
            devices = copy.deepcopy(self.devices_state)
        
        count = 0
        for pc_name, data in devices.items():
            # CORRECCIÓN: Llamada correcta al método existente
            self.service.upsert_device(data)
            
            if force_history:
                self.service.add_latency_record(data)
                with self.lock:
                    if pc_name in self.devices_state:
                        self.devices_state[pc_name]['_last_latency_sync'] = datetime.now()
            count += 1
