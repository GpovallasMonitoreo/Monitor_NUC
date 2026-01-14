import time
import threading
import statistics
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# CONFIGURACIÓN DE AHORRO DE DATOS
CONFIG = {
    'aggregation_window': 900,      # 15 minutos: Tiempo para guardar el promedio
    'latency_spike_threshold': 2.0, # Sensibilidad: Si el ping se duplica, guarda YA
    'packet_loss_critical': 1,      # Si se pierde 1 paquete, guarda YA
    'offline_timeout': 600,         # 10 minutos sin señal = Offline
    'periodic_sync_status': 300     # 5 minutos: Actualizar "Last Seen" en tabla devices
}

class DeviceMonitorManager:
    """
    Gestor que agrupa métricas en memoria y solo envía a la DB 
    resúmenes estadísticos o alertas críticas.
    """
    def __init__(self, db_service, storage_service):
        self.db = db_service
        self.storage = storage_service
        
        # Estado actual (última foto para dashboard)
        self.devices_state: Dict[str, Dict] = {}
        
        # Buffer de Agregación: { 'device_id': { 'pings': [], 'loss': 0, 'start': datetime } }
        self.latency_buffer: Dict[str, Dict] = {}
        
        self.running = False
        self.lock = threading.Lock()
        self.monitor_thread = threading.Thread(target=self._background_loop, daemon=True)

    def start(self):
        if not self.running:
            self.running = True
            self.monitor_thread.start()
            logger.info("🚀 Monitor Inteligente iniciado (Modo Agregación Activado)")

    def stop(self):
        self.running = False

    def ingest_data(self, device_data: Dict[str, Any]):
        """Recibe datos del agente PC."""
        device_id = device_data.get('mac_address') or device_data.get('pc_name')
        if not device_id: return

        now = datetime.now()
        latency = device_data.get('latency_ms')
        packet_loss = device_data.get('packet_loss', 0)

        with self.lock:
            # 1. Actualizar RAM (para Dashboard en tiempo real)
            device_data['_last_seen_local'] = now
            self.devices_state[device_id] = device_data
            
            # 2. Procesar Latencia (Buffer Inteligente)
            if latency is not None:
                self._process_latency_smart(device_id, float(latency), packet_loss)

            # 3. Detectar Cambios de Estado (Online/Offline) -> Guardar Inmediato
            old_data = self.devices_state.get(device_id, {})
            if device_data.get('status') != old_data.get('status'):
                logger.info(f"⚡ Cambio de estado en {device_id}. Actualizando DB.")
                self._update_device_status_in_db(device_data)

    def _process_latency_smart(self, device_id: str, latency: float, packet_loss: int):
        """Decide si guardar inmediatamente o esperar."""
        
        # Inicializar buffer si es nuevo
        if device_id not in self.latency_buffer:
            self.latency_buffer[device_id] = {
                'pings': [],
                'packet_loss_accum': 0,
                'start_time': datetime.now()
            }
        
        buf = self.latency_buffer[device_id]
        
        # --- Detección de Anomalías (Spikes) ---
        is_spike = False
        
        # Regla 1: Pérdida de paquetes
        if packet_loss >= CONFIG['packet_loss_critical']:
            is_spike = True
            
        # Regla 2: Latencia se dispara (comparado con el promedio del buffer actual)
        if len(buf['pings']) > 5:
            current_avg = statistics.mean(buf['pings'])
            if current_avg > 0 and latency > (current_avg * CONFIG['latency_spike_threshold']) and latency > 100:
                is_spike = True

        # Agregar al buffer
        buf['pings'].append(latency)
        buf['packet_loss_accum'] += packet_loss

        # --- Decisión de Guardado ---
        time_diff = (datetime.now() - buf['start_time']).total_seconds()
        
        # Guardamos si: Es un pico O ya pasó el tiempo de ventana (15 min)
        if is_spike or time_diff >= CONFIG['aggregation_window']:
            reason = "SPIKE" if is_spike else "PERIODIC"
            self._flush_device_buffer(device_id, reason)

    def _flush_device_buffer(self, device_id: str, reason: str):
        """Calcula estadísticas y envía a Supabase."""
        if device_id not in self.latency_buffer: return
        
        buf = self.latency_buffer[device_id]
        if not buf['pings']: return

        # Matemáticas
        avg_lat = int(statistics.mean(buf['pings']))
        min_lat = int(min(buf['pings']))
        max_lat = int(max(buf['pings']))
        samples = len(buf['pings'])
        total_loss = buf['packet_loss_accum']

        try:
            # Enviamos a Supabase con metadatos extra
            self.db.buffer_metric(
                device_id=device_id,
                latency=avg_lat,
                packet_loss=total_loss,
                extra_data={
                    "min": min_lat,
                    "max": max_lat,
                    "samples": samples
                }
            )
            
            if reason == "SPIKE":
                logger.warning(f"📉 Pico detectado en {device_id}: {avg_lat}ms. Guardado inmediato.")
                
        except Exception as e:
            logger.error(f"Error flushing buffer: {e}")

        # Reiniciar buffer
        self.latency_buffer[device_id] = {
            'pings': [],
            'packet_loss_accum': 0,
            'start_time': datetime.now()
        }

    def _background_loop(self):
        """Tarea de fondo para Watchdog y limpieza de buffers viejos"""
        while self.running:
            try:
                now = datetime.now()
                self._check_offline_devices(now)
                
                # Revisar buffers que expiraron por tiempo
                with self.lock:
                    for dev_id in list(self.latency_buffer.keys()):
                        buf = self.latency_buffer[dev_id]
                        if (now - buf['start_time']).total_seconds() >= CONFIG['aggregation_window']:
                            self._flush_device_buffer(dev_id, "TIMEOUT")

                # Enviar datos pendientes a la nube (Batch de Supabase)
                if hasattr(self.db, '_flush_buffer'):
                    self.db._flush_buffer()
                
                # Sincronizar 'last_seen' periódicamente
                if (now - self.last_global_sync).total_seconds() >= CONFIG['periodic_sync_status']:
                     self._perform_bulk_status_update()
                     self.last_global_sync = now

                time.sleep(10)
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(30)
    
    # Inicializar variable de sync
    last_global_sync = datetime.now()

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
        """Actualiza solo el 'last_seen' en la tabla devices para que sepamos que siguen vivos"""
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
