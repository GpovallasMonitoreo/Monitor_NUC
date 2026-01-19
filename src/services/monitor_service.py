import time
import threading
import statistics
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# CONFIGURACIÓN
CONFIG = {
    'aggregation_window': 3600,     # 1 Hora
    'spike_multiplier': 1.5,
    'absolute_high_latency': 120,
    'packet_loss_critical': 1,
    'offline_timeout': 600,         # 10 minutos sin señal = Offline
    'periodic_sync_status': 300
}

class DeviceMonitorManager:
    def __init__(self, db_service, storage_service):
        self.db = db_service
        self.storage = storage_service
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
            logger.info("🚀 Monitor Iniciado: Sensores y Contadores Activos")

    def stop(self):
        self.running = False

    def ingest_data(self, device_data: Dict[str, Any]):
        """Recibe datos del agente."""
        device_id = device_data.get('mac_address') or device_data.get('pc_name')
        if not device_id: return

        now = datetime.now()
        try: latency = float(device_data.get('latency_ms', 0))
        except: latency = 0.0
        packet_loss = int(device_data.get('packet_loss', 0))

        with self.lock:
            # Recuperar estado anterior para no perder el contador de desconexiones
            old_data = self.devices_state.get(device_id, {})
            current_disconnects = old_data.get('disconnect_count', 0)
            
            # Actualizar datos en memoria
            device_data['_last_seen_local'] = now
            # Mantenemos el contador histórico
            device_data['disconnect_count'] = current_disconnects 
            
            # GUARDAR SENSORES: Aseguramos que el campo 'extended_sensors' se guarde
            if 'extended_sensors' in device_data:
                # Normalizamos para que siempre viaje como 'extended_sensors'
                pass 

            self.devices_state[device_id] = device_data
            
            # Buffer de Latencia
            if latency > 0 or packet_loss > 0:
                self._process_latency_smart(device_id, latency, packet_loss)

            # Detectar cambios de estado
            if device_data.get('status') != old_data.get('status'):
                self._update_device_status_in_db(device_data)

    def _process_latency_smart(self, device_id: str, latency: float, packet_loss: int):
        if device_id not in self.latency_buffer:
            self.latency_buffer[device_id] = {'pings': [], 'packet_loss_accum': 0, 'start_time': datetime.now()}
        
        buf = self.latency_buffer[device_id]
        should_flush = False
        reason = "HOURLY"
        
        if packet_loss >= CONFIG['packet_loss_critical']:
            should_flush = True
            reason = "PACKET_LOSS"
        elif latency >= CONFIG['absolute_high_latency']:
            should_flush = True
            reason = "HIGH_LATENCY"
        elif len(buf['pings']) >= 5:
            avg = statistics.mean(buf['pings'])
            if latency > 50 and latency > (avg * CONFIG['spike_multiplier']):
                should_flush = True
                reason = "SPIKE"

        if (datetime.now() - buf['start_time']).total_seconds() >= CONFIG['aggregation_window']:
            should_flush = True

        buf['pings'].append(latency)
        buf['packet_loss_accum'] += packet_loss

        if should_flush:
            self._flush_device_buffer(device_id, reason)

    def _flush_device_buffer(self, device_id: str, reason: str):
        if device_id not in self.latency_buffer: return
        buf = self.latency_buffer[device_id]
        if not buf['pings']: return

        avg = int(statistics.mean(buf['pings']))
        try:
            self.db.buffer_metric(
                device_id=device_id,
                latency=avg,
                packet_loss=buf['packet_loss_accum'],
                extra_data={"min": int(min(buf['pings'])), "max": int(max(buf['pings'])), "samples": len(buf['pings'])}
            )
        except Exception as e:
            logger.error(f"Error flush: {e}")

        self.latency_buffer[device_id] = {'pings': [], 'packet_loss_accum': 0, 'start_time': datetime.now()}

    def _background_loop(self):
        while self.running:
            try:
                now = datetime.now()
                self._check_offline_devices(now)
                
                # Barrido de seguridad
                with self.lock:
                    for dev_id in list(self.latency_buffer.keys()):
                        buf = self.latency_buffer[dev_id]
                        if (now - buf['start_time']).total_seconds() >= CONFIG['aggregation_window']:
                            self._flush_device_buffer(dev_id, "TIMEOUT_CHECK")

                if hasattr(self.db, '_flush_buffer'): self.db._flush_buffer()
                
                if (now - self.last_global_sync).total_seconds() >= CONFIG['periodic_sync_status']:
                     self._perform_bulk_status_update()
                     self.last_global_sync = now
                time.sleep(10)
            except Exception as e:
                logger.error(f"Loop error: {e}")
                time.sleep(30)
    
    def _check_offline_devices(self, now):
        with self.lock:
            for dev_id, data in self.devices_state.items():
                last_seen = data.get('_last_seen_local')
                if not last_seen: continue
                
                if (now - last_seen).total_seconds() > CONFIG['offline_timeout']:
                    if data.get('status') != 'offline':
                        # MARCAR COMO OFFLINE
                        data['status'] = 'offline'
                        
                        # INCREMENTAR CONTADOR DE DESCONEXIONES
                        old_count = data.get('disconnect_count', 0)
                        data['disconnect_count'] = old_count + 1
                        
                        logger.warning(f"💀 {data.get('pc_name')} OFFLINE (Caída #{data['disconnect_count']})")
                        self._update_device_status_in_db(data)

    def _perform_bulk_status_update(self):
        with self.lock:
            devices = list(self.devices_state.values())
        for dev in devices:
            self._update_device_status_in_db(dev)

    def _update_device_status_in_db(self, data):
        """Envía estado, sensores y contadores a Supabase"""
        if hasattr(self.db, 'upsert_device_status'):
            self.db.upsert_device_status({
                "device_id": data.get('mac_address') or data.get('pc_name'),
                "pc_name": data.get('pc_name'),
                "status": data.get('status'),
                "ip_address": data.get('ip_address'),
                "cpu_load": data.get('cpu_load_percent'),
                "ram_usage": data.get('ram_percent'), # Agregamos RAM
                "last_seen": datetime.utcnow().isoformat(),
                # AQUÍ ESTÁN LOS CAMPOS NUEVOS:
                "sensors": data.get('extended_sensors'), # Guardamos el JSON de sensores
                "disconnect_count": data.get('disconnect_count', 0)
            })
