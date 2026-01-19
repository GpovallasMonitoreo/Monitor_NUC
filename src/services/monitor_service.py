import time
import threading
import statistics
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# CONFIGURACIÓN (Basada en tu snippet)
CONFIG = {
    'aggregation_window': 3600,     # 1 Hora
    'spike_multiplier': 1.5,
    'absolute_high_latency': 120,
    'packet_loss_critical': 1,
    'offline_timeout': 600,         # 10 minutos sin señal = Offline
    'periodic_sync_status': 300
}

class DeviceMonitorManager:
    def __init__(self, db_service):
        self.db = db_service
        self.devices_state: Dict[str, Dict] = {}
        self.latency_buffer: Dict[str, Dict] = {}
        self.running = False
        self.lock = threading.Lock()
        self.monitor_thread = threading.Thread(target=self._background_loop, daemon=True)
        self.last_global_sync = datetime.now()

    def start(self):
        if not self.running:
            self.running = True
            self.monitor_thread.start()
            logger.info("🚀 Monitor Argos Activo: Sensores y Contadores")

    def ingest_data(self, device_data: Dict[str, Any]):
        """Recibe datos del agente."""
        # Priorizamos pc_name como ID según tu lógica
        device_id = device_data.get('pc_name')
        if not device_id: return

        now = datetime.now()
        try: latency = float(device_data.get('latency_ms', 0))
        except: latency = 0.0
        packet_loss = int(device_data.get('packet_loss', 0))

        with self.lock:
            old_data = self.devices_state.get(device_id, {})
            # Preservamos el estado de conexión previo para detectar cambios
            was_offline = old_data.get('status') == 'offline'
            current_disconnects = old_data.get('disconnect_count', 0)
            
            # Actualización de estado
            device_data['_last_seen_local'] = now
            device_data['disconnect_count'] = current_disconnects
            
            # Si vuelve de estar offline, marcamos como online
            if was_offline:
                device_data['status'] = 'online'

            self.devices_state[device_id] = device_data
            
            # Procesamiento inteligente de latencia (Smart Flush)
            if latency > 0 or packet_loss > 0:
                self._process_latency_smart(device_id, latency, packet_loss)

            # Sincronización inmediata si el estado cambió
            if device_data.get('status') != old_data.get('status'):
                self._update_device_status_in_db(device_data)

    def _process_latency_smart(self, device_id: str, latency: float, packet_loss: int):
        if device_id not in self.latency_buffer:
            self.latency_buffer[device_id] = {'pings': [], 'packet_loss_accum': 0, 'start_time': datetime.now()}
        
        buf = self.latency_buffer[device_id]
        should_flush = False
        reason = "PERIODIC"
        
        if packet_loss >= CONFIG['packet_loss_critical']:
            should_flush = True; reason = "LOSS"
        elif latency >= CONFIG['absolute_high_latency']:
            should_flush = True; reason = "HIGH"
        elif len(buf['pings']) >= 5:
            avg = statistics.mean(buf['pings'])
            if latency > 50 and latency > (avg * CONFIG['spike_multiplier']):
                should_flush = True; reason = "SPIKE"

        if (datetime.now() - buf['start_time']).total_seconds() >= CONFIG['aggregation_window']:
            should_flush = True

        buf['pings'].append(latency)
        buf['packet_loss_accum'] += packet_loss

        if should_flush:
            self._flush_device_buffer(device_id, reason)

    def _flush_device_buffer(self, device_id: str, reason: str):
        buf = self.latency_buffer.get(device_id)
        if not buf or not buf['pings']: return
        
        avg = int(statistics.mean(buf['pings']))
        # Aquí enviamos la métrica histórica a la DB
        self.db.save_latency_history(device_id, avg, buf['packet_loss_accum'], reason)
        self.latency_buffer[device_id] = {'pings': [], 'packet_loss_accum': 0, 'start_time': datetime.now()}

    def _background_loop(self):
        while self.running:
            try:
                now = datetime.now()
                self._check_offline_devices(now)
                
                # Sincronización global periódica
                if (now - self.last_global_sync).total_seconds() >= CONFIG['periodic_sync_status']:
                    self._perform_bulk_status_update()
                    self.last_global_sync = now
                time.sleep(10)
            except Exception as e:
                logger.error(f"Error loop: {e}")
                time.sleep(30)

    def _check_offline_devices(self, now):
        with self.lock:
            for dev_id, data in self.devices_state.items():
                last_seen = data.get('_last_seen_local')
                if last_seen and (now - last_seen).total_seconds() > CONFIG['offline_timeout']:
                    if data.get('status') != 'offline':
                        data['status'] = 'offline'
                        data['disconnect_count'] = data.get('disconnect_count', 0) + 1
                        logger.warning(f"💀 {data.get('pc_name')} OFFLINE (Caída #{data['disconnect_count']})")
                        self._update_device_status_in_db(data)

    def _perform_bulk_status_update(self):
        with self.lock:
            for dev in self.devices_state.values():
                self._update_device_status_in_db(dev)

    def _update_device_status_in_db(self, data):
        # Mapeo a tu esquema de Supabase
        payload = {
            "device_id": data.get('pc_name'),
            "pc_name": data.get('pc_name'),
            "status": data.get('status'),
            "ip_address": data.get('ip'),
            "cpu_load": data.get('cpu_load_percent'),
            "ram_usage": data.get('ram_percent'),
            "last_seen": datetime.utcnow().isoformat(),
            "sensors": data.get('extended_sensors'),
            "disconnect_count": data.get('disconnect_count', 0)
        }
        self.db.upsert_device_status(payload)
