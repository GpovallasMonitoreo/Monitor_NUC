import time
import threading
import statistics
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN AJUSTADA (MÁS SENSIBLE) ---
CONFIG = {
    'aggregation_window': 900,      # 15 minutos: Tiempo máximo de espera si todo está bien
    'spike_multiplier': 1.5,        # Antes 2.0. Ahora: Si el ping sube 50%, guarda YA.
    'absolute_high_latency': 150,   # NUEVO: Si pasa de 150ms, guarda SIEMPRE (es lag).
    'packet_loss_critical': 1,      # Si se pierde 1 paquete, guarda YA.
    'offline_timeout': 600,         # 10 minutos sin señal = Offline
    'periodic_sync_status': 300     # 5 minutos: Heartbeat a la DB
}

class DeviceMonitorManager:
    def __init__(self, db_service, storage_service):
        self.db = db_service
        self.storage = storage_service
        self.devices_state: Dict[str, Dict] = {}
        self.latency_buffer: Dict[str, Dict] = {} # Buffer de Agregación
        self.running = False
        self.lock = threading.Lock()
        self.monitor_thread = threading.Thread(target=self._background_loop, daemon=True)
        self.last_global_sync = datetime.now()

    def start(self):
        if not self.running:
            self.running = True
            self.monitor_thread.start()
            logger.info("🚀 Monitor v2.1: Sensibilidad Aumentada")

    def stop(self):
        self.running = False

    def ingest_data(self, device_data: Dict[str, Any]):
        """Recibe datos del agente."""
        device_id = device_data.get('mac_address') or device_data.get('pc_name')
        if not device_id: return

        now = datetime.now()
        # Aseguramos que latency_ms sea un número
        try:
            latency = float(device_data.get('latency_ms', 0))
        except:
            latency = 0.0
            
        packet_loss = int(device_data.get('packet_loss', 0))

        with self.lock:
            # 1. Actualizar RAM (Tiempo Real)
            device_data['_last_seen_local'] = now
            self.devices_state[device_id] = device_data
            
            # 2. Procesar Latencia (Buffer vs DB)
            if latency > 0:
                self._process_latency_smart(device_id, latency, packet_loss)

            # 3. Detectar Cambios de Estado (Online/Offline) -> Guardar Inmediato
            old_data = self.devices_state.get(device_id, {})
            if device_data.get('status') != old_data.get('status'):
                logger.info(f"⚡ Cambio de estado en {device_id}. Actualizando DB.")
                self._update_device_status_in_db(device_data)

    def _process_latency_smart(self, device_id: str, latency: float, packet_loss: int):
        """Decide si guardar inmediatamente o esperar."""
        
        # Inicializar buffer
        if device_id not in self.latency_buffer:
            self.latency_buffer[device_id] = {
                'pings': [],
                'packet_loss_accum': 0,
                'start_time': datetime.now()
            }
        
        buf = self.latency_buffer[device_id]
        
        # --- LÓGICA DE DECISIÓN (EL CEREBRO) ---
        should_flush = False
        reason = "PERIODIC"
        
        # 1. ¿Hay pérdida de paquetes? -> CRÍTICO
        if packet_loss >= CONFIG['packet_loss_critical']:
            should_flush = True
            reason = "PACKET_LOSS"
            
        # 2. ¿La latencia es objetivamente mala? (> 150ms) -> LAG
        elif latency >= CONFIG['absolute_high_latency']:
            should_flush = True
            reason = "HIGH_LATENCY"
            
        # 3. ¿Es un pico relativo? (Subió 50% respecto al promedio reciente)
        elif len(buf['pings']) >= 3: # Con 3 muestras ya calculamos
            current_avg = statistics.mean(buf['pings'])
            # Solo consideramos picos si la latencia base es al menos 50ms 
            # (para evitar alertas porque subió de 5ms a 8ms)
            if latency > 50 and latency > (current_avg * CONFIG['spike_multiplier']):
                should_flush = True
                reason = "SPIKE"

        # 4. ¿Pasó el tiempo de espera (15 min)? -> RUTINA
        time_diff = (datetime.now() - buf['start_time']).total_seconds()
        if time_diff >= CONFIG['aggregation_window']:
            should_flush = True
            reason = "PERIODIC"

        # --- ACCIÓN ---
        # Agregamos al buffer SIEMPRE para la estadística
        buf['pings'].append(latency)
        buf['packet_loss_accum'] += packet_loss

        # Si toca guardar, enviamos y limpiamos
        if should_flush:
            self._flush_device_buffer(device_id, reason)

    def _flush_device_buffer(self, device_id: str, reason: str):
        """Calcula estadísticas y envía a Supabase."""
        if device_id not in self.latency_buffer: return
        
        buf = self.latency_buffer[device_id]
        if not buf['pings']: return

        avg_lat = int(statistics.mean(buf['pings']))
        min_lat = int(min(buf['pings']))
        max_lat = int(max(buf['pings']))
        samples = len(buf['pings'])
        total_loss = buf['packet_loss_accum']

        try:
            # Enviamos a Supabase
            self.db.buffer_metric(
                device_id=device_id,
                latency=avg_lat, # Guardamos el promedio de la ventana
                packet_loss=total_loss,
                extra_data={
                    "min": min_lat,
                    "max": max_lat,
                    "samples": samples
                }
            )
            
            # Loguear solo si fue un evento interesante
            if reason in ["SPIKE", "HIGH_LATENCY", "PACKET_LOSS"]:
                logger.info(f"📉 Evento {reason} en {device_id}: {avg_lat}ms (Max: {max_lat}). Guardado.")
                
        except Exception as e:
            logger.error(f"Error flushing buffer: {e}")

        # Reiniciar buffer (¡IMPORTANTE!)
        # Reiniciamos el timer y vaciamos la lista para empezar a medir el siguiente periodo
        self.latency_buffer[device_id] = {
            'pings': [],
            'packet_loss_accum': 0,
            'start_time': datetime.now()
        }

    def _background_loop(self):
        while self.running:
            try:
                now = datetime.now()
                self._check_offline_devices(now)
                
                # Barrido de seguridad por si algún buffer se quedó atascado
                with self.lock:
                    for dev_id in list(self.latency_buffer.keys()):
                        buf = self.latency_buffer[dev_id]
                        if (now - buf['start_time']).total_seconds() >= CONFIG['aggregation_window']:
                            self._flush_device_buffer(dev_id, "TIMEOUT_CHECK")

                if hasattr(self.db, '_flush_buffer'):
                    self.db._flush_buffer()
                
                if (now - self.last_global_sync).total_seconds() >= CONFIG['periodic_sync_status']:
                     self._perform_bulk_status_update()
                     self.last_global_sync = now

                time.sleep(5) # Revisamos cada 5s para mayor precisión
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(30)
    
    def _check_offline_devices(self, now):
        with self.lock:
            for dev_id, data in self.devices_state.items():
                last_seen = data.get('_last_seen_local')
                if not last_seen: continue
                
                if (now - last_seen).total_seconds() > CONFIG['offline_timeout']:
                    if data.get('status') != 'offline':
                        data['status'] = 'offline'
                        logger.warning(f"💀 Watchdog: {data.get('pc_name')} OFFLINE")
                        self._update_device_status_in_db(data)

    def _perform_bulk_status_update(self):
        with self.lock:
            devices = list(self.devices_state.values())
        for dev in devices:
            self._update_device_status_in_db(dev)

    def _update_device_status_in_db(self, data):
        if hasattr(self.db, 'upsert_device_status'):
            self.db.upsert_device_status({
                "device_id": data.get('mac_address') or data.get('pc_name'),
                "pc_name": data.get('pc_name'),
                "status": data.get('status'),
                "ip_address": data.get('ip_address'),
                "cpu_load": data.get('cpu_load_percent'),
                "last_seen": datetime.utcnow().isoformat()
            })
