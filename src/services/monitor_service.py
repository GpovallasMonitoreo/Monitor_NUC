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
    'offline_timeout': 600,  # 10 minutos sin señal = Offline
    'periodic_sync': 300,    # 5 minutos: Actualizar estado "Seen Last" en DB
}

logger = logging.getLogger(__name__)

class DeviceMonitorManager:
    """
    Gestor que orquesta la monitorización y el envío a Supabase.
    """

    def __init__(self, db_service, storage_service):
        self.db = db_service           # SupabaseService
        self.storage = storage_service # StorageService (Local + Alertas)
        
        self.devices_state: Dict[str, Dict] = {} 
        self.running = False
        self.lock = threading.Lock()
        self.last_global_sync = datetime.now()
        
        # Hilo en segundo plano
        self.monitor_thread = threading.Thread(target=self._background_loop, daemon=True)

    def start(self):
        if not self.running:
            self.running = True
            self.monitor_thread.start()
            logger.info("🚀 MonitorManager iniciado (Backend: Supabase)")

    def stop(self):
        self.running = False
        logger.info("🛑 MonitorManager detenido")

    def ingest_data(self, device_data: Dict[str, Any]):
        """
        Recibe datos del agente instalado en la PC.
        """
        # Asegurar que tenemos un ID único. Usamos mac_address o pc_name.
        device_id = device_data.get('mac_address') or device_data.get('pc_name')
        if not device_id: return

        pc_name = device_data.get('pc_name', 'Unknown')

        with self.lock:
            # 1. Recuperar estado anterior de la RAM
            old_data = self.devices_state.get(device_id, {})
            
            # 2. Detectar cambios bruscos (CPU, Status, etc)
            is_urgent = self._check_sudden_changes(device_data, old_data)
            
            # 3. Actualizar timestamp local
            now = datetime.now()
            device_data['_last_seen_local'] = now
            
            # 4. Guardar en RAM
            self.devices_state[device_id] = device_data

        # --- LÓGICA DE ENVÍO A SUPABASE ---

        # A. MÉTRICAS (Historial):
        # Enviamos SIEMPRE al buffer. La clase SupabaseService se encarga de 
        # juntar 50 registros antes de hacer la petición a internet.
        try:
            self.db.buffer_metric(
                device_id=device_id,
                latency=device_data.get('latency_ms', 0),
                packet_loss=device_data.get('packet_loss', 0)
            )
        except Exception as e:
            logger.debug(f"Error buffer metrics: {e}")

        # B. ESTADO DEL DISPOSITIVO (Tabla Devices):
        # Si es urgente (cambio de status, CPU pico) o pasó mucho tiempo, actualizamos la tabla de inventario.
        if is_urgent:
            logger.info(f"⚡ Cambio urgente en {pc_name}. Actualizando DB.")
            self._update_device_status_in_db(device_data)

    def force_manual_sync(self):
        """
        Botón 'Refrescar' de la web: Fuerza actualización de estados.
        """
        logger.info("🔄 Sincronización manual solicitada")
        self._perform_bulk_sync()

    def _background_loop(self):
        """Ciclo infinito que corre en segundo plano"""
        while self.running:
            try:
                now = datetime.now()
                
                # 1. Chequeo de dispositivos caídos (Watchdog)
                self._check_offline_devices(now)

                # 2. Sincronización periódica (Heartbeat a la DB)
                # Actualiza el campo "last_seen" en la nube cada X minutos
                if (now - self.last_global_sync).total_seconds() >= THRESHOLDS['periodic_sync']:
                    self._perform_bulk_sync()
                    self.last_global_sync = now
                
                # 3. Flushear el buffer de métricas si quedó algo pendiente
                # (Por si no llegaron a 50 registros)
                if hasattr(self.db, '_flush_buffer'):
                    self.db._flush_buffer()

                time.sleep(10) # Loop tranquilo cada 10s
            except Exception as e:
                logger.error(f"Error en monitor loop: {e}")
                time.sleep(30)

    def _check_sudden_changes(self, new_data: Dict, old_data: Dict) -> bool:
        """Determina si vale la pena actualizar la tabla de estado YA MISMO"""
        if not old_data: return True 
        
        # Cambio de status (Online -> Busy)
        if new_data.get('status') != old_data.get('status'): return True
        
        # Pico de CPU
        try:
            cpu_diff = abs(float(new_data.get('cpu_load_percent', 0)) - float(old_data.get('cpu_load_percent', 0)))
            if cpu_diff > THRESHOLDS['cpu_spike']: return True
        except: pass
        
        return False

    def _check_offline_devices(self, now: datetime):
        """Marca como OFFLINE los equipos que no han reportado"""
        with self.lock:
            for dev_id, data in self.devices_state.items():
                last_seen = data.get('_last_seen_local')
                if not last_seen: continue
                
                # Si pasó el tiempo límite
                if (now - last_seen).total_seconds() > THRESHOLDS['offline_timeout']:
                    if data.get('status') != 'offline':
                        logger.warning(f"💀 Watchdog: {data.get('pc_name')} OFFLINE")
                        
                        # 1. Cambiar estado local
                        data['status'] = 'offline'
                        
                        # 2. Actualizar DB Nube
                        self._update_device_status_in_db(data)
                        
                        # 3. Generar Alerta (Usando el servicio de storage que tiene alerts)
                        if self.storage and hasattr(self.storage, 'alert_service'):
                            self.storage.alert_service.create_alert(
                                device_id=dev_id,
                                type_alert="watchdog_offline",
                                msg=f"Dispositivo {data.get('pc_name')} dejó de responder",
                                sev="high"
                            )

    def _perform_bulk_sync(self):
        """Actualiza el estado (tabla devices) de todos los equipos en memoria"""
        with self.lock:
            devices = copy.deepcopy(self.devices_state)
        
        for _, data in devices.items():
            self._update_device_status_in_db(data)

    def _update_device_status_in_db(self, device_data):
        """
        Helper para hacer UPSERT en la tabla 'devices' de Supabase.
        """
        try:
            # Preparamos el objeto plano para la DB
            payload = {
                "device_id": device_data.get('mac_address') or device_data.get('pc_name'),
                "pc_name": device_data.get('pc_name'),
                "ip_address": device_data.get('ip_address'),
                "status": device_data.get('status'),
                "cpu_load": device_data.get('cpu_load_percent'),
                "ram_usage": device_data.get('ram_load_percent'),
                "last_seen": datetime.utcnow().isoformat(),
                "location": device_data.get('location', 'Unknown')
            }
            
            # Usamos el cliente raw de Supabase si no hay método específico
            if hasattr(self.db, 'upsert_device_status'):
                self.db.upsert_device_status(payload)
            elif hasattr(self.db, 'client'):
                self.db.client.table('devices').upsert(payload).execute()
                
        except Exception as e:
            logger.error(f"Error actualizando status DB: {e}")
            
