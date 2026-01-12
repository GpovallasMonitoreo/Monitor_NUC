import time
import threading
import copy
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuración de umbrales para "cambios bruscos"
THRESHOLDS = {
    'cpu_spike': 40.0,       # Si la CPU sube un 40% de golpe
    'temp_spike': 15.0,      # Si la temperatura sube 15°C de golpe
    'disk_spike': 20.0,      # Cambio brusco en uso de disco
    'offline_timeout': 600,  # 10 minutos en segundos
    'periodic_sync': 900     # 15 minutos en segundos
}

class DeviceMonitorManager:
    """
    Gestor que orquesta el AppSheetService y maneja la lógica de negocio:
    - Ciclos automáticos (15 min)
    - Detección de anomalías (Cambios bruscos)
    - Watchdog (Offline > 10 min)
    """

    def __init__(self, appsheet_service: AppSheetService):
        self.service = appsheet_service
        self.devices_state: Dict[str, Dict] = {} # Memoria local del estado actual
        self.running = False
        self.lock = threading.Lock() # Para evitar conflictos entre hilos
        
        # Timers
        self.last_global_sync = datetime.now()
        
        # Hilo de fondo
        self.monitor_thread = threading.Thread(target=self._background_loop, daemon=True)

    def start(self):
        """Inicia el monitoreo en segundo plano"""
        if not self.running:
            self.running = True
            self.monitor_thread.start()
            logger.info("🚀 MonitorManager iniciado: Watchdog y Sync activados.")

    def stop(self):
        """Detiene el monitoreo"""
        self.running = False
        logger.info("🛑 MonitorManager detenido.")

    def ingest_data(self, device_data: Dict[str, Any]):
        """
        Punto de entrada: Recibe datos de un NUC (desde tu agente o script de recolección).
        Aquí detectamos los "cambios bruscos" inmediatamente.
        """
        pc_name = device_data.get('pc_name')
        if not pc_name:
            return

        with self.lock:
            # 1. Verificar si hay cambios bruscos respecto al último dato
            is_urgent = self._check_sudden_changes(pc_name, device_data)
            
            # 2. Actualizar memoria local
            current_time = datetime.now()
            device_data['_last_seen_local'] = current_time
            
            # Si no existía, lo marcamos para sync inmediata
            if pc_name not in self.devices_state:
                is_urgent = True 

            self.devices_state[pc_name] = device_data

        # 3. Si es urgente (cambio brusco o nuevo), sincronizamos YA.
        if is_urgent:
            logger.warning(f"⚡ Cambio brusco detectado en {pc_name}. Forzando sync.")
            self.service.sync_device_complete(device_data)
        else:
            # Si no es urgente, solo guardamos en memoria. 
            # El ciclo de 15 min se encargará de subirlo, o podemos subir solo latencia ligera.
            # Opcional: Subir latencia siempre para historial continuo
            self.service.add_latency_record(device_data)

    def force_manual_sync(self):
        """Requerimiento: Actualización Manual"""
        logger.info("🔄 Ejecutando sincronización manual solicitada...")
        self._perform_bulk_sync()

    def _background_loop(self):
        """Bucle infinito que revisa tiempos cada 10 segundos"""
        while self.running:
            try:
                now = datetime.now()
                
                # A. Chequeo de Watchdog (Offline > 10 min)
                self._check_offline_devices(now)

                # B. Chequeo de Sincronización Periódica (15 min)
                time_since_sync = (now - self.last_global_sync).total_seconds()
                if time_since_sync >= THRESHOLDS['periodic_sync']:
                    logger.info("⏰ Ejecutando sincronización programada de 15 min...")
                    self._perform_bulk_sync()
                    self.last_global_sync = now
                
                time.sleep(10) # Dormir 10 segundos para no saturar CPU
                
            except Exception as e:
                logger.error(f"❌ Error en bucle de monitoreo: {e}")
                time.sleep(30)

    def _check_sudden_changes(self, pc_name: str, new_data: Dict) -> bool:
        """Compara datos nuevos con anteriores para ver si vale la pena alertar"""
        if pc_name not in self.devices_state:
            return False

        old_data = self.devices_state[pc_name]
        urgent = False

        # Comprobar CPU
        cpu_diff = abs(new_data.get('cpu_load_percent', 0) - old_data.get('cpu_load_percent', 0))
        if cpu_diff > THRESHOLDS['cpu_spike']:
            logger.warning(f"📈 Pico de CPU en {pc_name}: {cpu_diff}% de cambio")
            urgent = True

        # Comprobar Temperatura (usando tu lógica de get_temp o el valor directo)
        temp_new = new_data.get('temperature', 0)
        temp_old = old_data.get('temperature', 0)
        if abs(temp_new - temp_old) > THRESHOLDS['temp_spike']:
            logger.warning(f"🔥 Pico de Temperatura en {pc_name}")
            urgent = True

        # Comprobar estado explícito (si cambia de online a critical, por ejemplo)
        if new_data.get('status') != old_data.get('status'):
            logger.info(f"🔄 Cambio de estado en {pc_name}: {old_data.get('status')} -> {new_data.get('status')}")
            urgent = True

        return urgent

    def _check_offline_devices(self, now: datetime):
        """
        Revisa si algún dispositivo no ha reportado en 10 min.
        Si pasa, actualizamos su estado a 'offline' en AppSheet y generamos alerta.
        """
        with self.lock:
            for pc_name, data in self.devices_state.items():
                last_seen = data.get('_last_seen_local')
                current_status = data.get('status', 'online')

                if not last_seen:
                    continue

                # Tiempo sin reportar
                seconds_silence = (now - last_seen).total_seconds()

                if seconds_silence > THRESHOLDS['offline_timeout'] and current_status != 'offline':
                    logger.error(f"💀 Watchdog: {pc_name} no responde hace {int(seconds_silence)}s. Marcando OFFLINE.")
                    
                    # 1. Actualizar estado local
                    data['status'] = 'offline'
                    data['unit'] = 'OFFLINE_AUTO' # Opcional: marca visual
                    
                    # 2. Forzar actualización a AppSheet
                    self.service.upsert_device(data)
                    self.service.add_alert(
                        data, 
                        alert_type="watchdog_offline", 
                        message=f"Dispositivo dejó de responder (Silence > 10m). Última vez: {last_seen}",
                        severity="high"
                    )

    def _perform_bulk_sync(self):
        """Sincroniza todos los dispositivos conocidos"""
        with self.lock:
            devices_snapshot = copy.deepcopy(self.devices_state)
        
        count = 0
        for pc_name, data in devices_snapshot.items():
            # Actualizamos la info estática del dispositivo
            self.service.upsert_device(data)
            count += 1
        
        logger.info(f"✅ Sincronización masiva completada: {count} dispositivos actualizados.")
