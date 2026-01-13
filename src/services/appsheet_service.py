import os
import requests
import json
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# Configuración de Zona Horaria
TZ_MX = ZoneInfo("America/Mexico_City")
logger = logging.getLogger(__name__)

class AppSheetService:
    """
    Servicio para AppSheet API v2 - VERSIÓN ARGOS FINAL
    Alineado estrictamente con las capturas de pantalla de las tablas.
    """
    
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY', '')
        self.app_id = os.getenv('APPSHEET_APP_ID', '')
        self.base_url = "https://api.appsheet.com/api/v2"
        
        env_enabled = os.getenv('APPSHEET_ENABLED', 'false').lower()
        is_config_enabled = env_enabled in ['true', '1', 'yes', 'on']
        has_creds = self.api_key and self.app_id and 'tu_api_key' not in self.api_key

        if not is_config_enabled or not has_creds:
            self.enabled = False
            logger.warning("⚠️ AppSheetService deshabilitado - Credenciales faltantes o flag apagada")
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService Listo (Modo DB-Strict) - App: {self.app_id[:8]}...")

    def _make_appsheet_request(self, table: str, action: str, rows: List[Dict] = None) -> Optional[Any]:
        """Envía petición HTTP a la API"""
        try:
            if not self.enabled: return None
            
            payload = {
                "Action": action, 
                "Properties": {
                    "Locale": "es-MX",
                    "Timezone": "Central Standard Time"
                }
            }
            if rows: payload["Rows"] = rows
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            # Timeout de 30s para evitar bloqueos
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                self.last_sync_time = datetime.now(TZ_MX)
                return response.json()
            
            # Manejo detallado de errores
            logger.error(f"❌ AppSheet Error {response.status_code} en tabla '{table}':")
            try:
                logger.error(f"   Detalle: {response.json()}")
            except:
                logger.error(f"   Respuesta Raw: {response.text}")
            
            return None
            
        except Exception as e:
            logger.error(f"🔥 Error crítico conexión AppSheet: {e}")
            return None

    def generate_device_id(self, pc_name: str) -> str:
        """Genera ID Hash MD5 consistente"""
        try:
            if not pc_name: return "UNKNOWN"
            clean_name = pc_name.strip().upper()
            # Lógica para nombres tipo MX_
            if clean_name.startswith("MX_") and len(clean_name.split(' ')[0]) > 3:
                return clean_name.split(' ')[0].strip()
            # Hash genérico
            return f"HASH_{hashlib.md5(clean_name.encode()).hexdigest()[:12].upper()}"
        except: return "ERROR_ID"

    # ==========================================================
    # 1. TABLA DEVICES (MAESTRA)
    # ==========================================================
    def get_or_create_device(self, device_data: Dict) -> tuple:
        """
        Sincroniza con la tabla 'devices'.
        Columnas basadas en imagen: device_id, pc_name, unit, public_ip, last_known_location, updated_at
        """
        try:
            if not self.enabled: return False, None, False
            
            pc_name = device_data.get('pc_name', '').strip()
            if not pc_name: return False, None, False
            
            device_id = self.generate_device_id(pc_name)
            current_time = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            # Mapeo EXACTO a tu imagen de 'devices'
            device_row = {
                "device_id": device_id,
                "pc_name": pc_name,
                "unit": str(device_data.get('unit', 'General')),
                "public_ip": str(device_data.get('public_ip', device_data.get('ip', ''))),
                "last_known_location": str(device_data.get('locName', pc_name)), # Mapeado a locName
                "updated_at": current_time
                # Nota: 'created_at' generalmente lo maneja AppSheet con Initial Value, 
                # pero si quieres forzarlo, añádelo aquí solo si es registro nuevo.
            }
            
            # Limpieza de Nulos (AppSheet prefiere strings vacíos a nulls en JSON)
            device_row = {k: (v if v is not None else "") for k, v in device_row.items()}
            
            # Usamos "Add" (AppSheet suele ser inteligente con Add para upserts si hay Key, 
            # pero lo ideal es "Edit" si ya existe. Por simplicidad usamos Add o un Action compuesto si tienes uno configurado)
            # Si Add falla por duplicado, podrías necesitar cambiar a "Edit" o configurar la tabla para "AllowUpdates"
            result = self._make_appsheet_request("devices", "Add", [device_row])
            
            return (result is not None), device_id, True
                
        except Exception as e:
            logger.error(f"Error get_or_create_device: {e}")
            return False, None, False

    # ==========================================================
    # 2. TABLA DEVICE_HISTORY (BITÁCORA)
    # ==========================================================
    def add_history_entry(self, log_data: Dict) -> bool:
        """
        Inserta en 'device_history'.
        Columnas basadas en imagen: device_name, pc_name, exec, action, what, desc, solved, locName, unit, status_snapshot, timestamp
        """
        try:
            if not self.enabled: return False
            dev_name = log_data.get('device_name') or log_data.get('pc_name')
            if not dev_name: return False

            # 1. Asegurar Padre
            success, _, _ = self.get_or_create_device({
                "pc_name": dev_name,
                "unit": log_data.get('unit', 'General'),
                "locName": log_data.get('locName', dev_name)
            })
            if not success:
                # Opcional: Loguear warning pero continuar si confías en que el padre existe
                logger.warning(f"⚠️ Padre no sincronizado para {dev_name}, intentando enviar historia de todas formas...")

            # 2. Preparar Payload
            # timestamp en formato AppSheet (YYYY-MM-DD HH:MM:SS)
            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')

            row = {
                "device_name": str(dev_name),
                "pc_name": str(dev_name),
                "exec": str(log_data.get('exec', '')),       # Antes 'executor'
                "action": str(log_data.get('action', 'Info')), # Antes 'action_type'
                "what": str(log_data.get('what', 'General')),  # Antes 'component'
                "desc": str(log_data.get('desc', '')),         # Antes 'description'
                "solved": str(log_data.get('solved', 'true')), # AppSheet a veces prefiere string "true"/"false" o "Y"/"N"
                "locName": str(log_data.get('locName', dev_name)),
                "unit": str(log_data.get('unit', 'General')),
                "status_snapshot": str(log_data.get('status_snapshot', 'active')),
                "timestamp": ts
                # "req": "" <-- ELIMINADO: No aparece en tus imágenes. Si existe, descomenta.
            }

            logger.info(f"📝 Enviando Bitácora: {dev_name} - {row['action']}")
            result = self._make_appsheet_request("device_history", "Add", [row])
            return result is not None

        except Exception as e:
            logger.error(f"Error add_history_entry: {e}")
            return False

    # ==========================================================
    # 3. TABLA LATENCY_HISTORY (MONITOREO)
    # ==========================================================
    def add_latency_to_history(self, device_data: Dict) -> bool:
        """
        Inserta en 'latency_history' (o Latency_history, check case sensitive)
        Columnas imagen: record_id, device_id, timestamp, latency..., cpu..., ram..., temp..., disk..., status, extended_sensors
        """
        try:
            if not self.enabled: return False
            pc_name = device_data.get('pc_name', '')
            if not pc_name: return False
            
            # Asegurar ID del padre
            device_id = self.generate_device_id(pc_name)
            
            record_id = str(uuid.uuid4())
            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            row = {
                "record_id": record_id,
                "device_id": device_id,
                "timestamp": ts,
                # Nombres abreviados basados en tu imagen (se cortan, asumo los standard)
                # Ajusta si tu columna real es 'latency_ms' o solo 'latency'
                "latency_ms": str(device_data.get('latency', 0)), 
                "cpu_load": str(device_data.get('cpu_load_percent', 0)), # Verifica si es cpu_usage o cpu_load
                "ram_usage": str(device_data.get('ram_percent', 0)),
                "temp_c": str(device_data.get('temperature', 0)),
                "disk_usage": str(device_data.get('disk_percent', 0)),
                "status": str(device_data.get('status', 'online')),
                "extended_sensors": str(device_data.get('extended_sensors', ''))[:2000]
            }
            
            # Nota: Verifica en AppSheet si la tabla se llama "latency_history" o "Latency_history" (mayúscula)
            result = self._make_appsheet_request("latency_history", "Add", [row])
            return result is not None
                
        except Exception:
            return False

    # ==========================================================
    # 4. TABLA ALERTS (NUEVA - Basada en imagen)
    # ==========================================================
    def add_alert(self, data: Dict, type_alert: str, msg: str, sev: str) -> bool:
        """
        Inserta en la tabla 'alerts' (Imagen image_2ebe32.png)
        Columnas: alert_id, device_id, alert_type, severity, message, timestamp, resolved_at
        """
        try:
            if not self.enabled: return False
            pc_name = data.get('pc_name', '')
            if not pc_name: return False

            device_id = self.generate_device_id(pc_name)
            alert_id = str(uuid.uuid4())
            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')

            row = {
                "alert_id": alert_id,
                "device_id": device_id,
                "alert_type": str(type_alert),
                "severity": str(sev),
                "message": str(msg),
                "timestamp": ts,
                "resolved_at": "" # Vacío inicialmente
            }

            logger.info(f"🚨 Enviando Alerta: {pc_name} - {type_alert}")
            result = self._make_appsheet_request("alerts", "Add", [row])
            return result is not None

        except Exception as e:
            logger.error(f"Error add_alert: {e}")
            return False

    # --- Métodos de Compatibilidad ---
    
    def sync_device_complete(self, data: Dict) -> bool:
        success, _, _ = self.get_or_create_device(data)
        return success
    
    def upsert_device(self, data: Dict) -> bool:
        return self.sync_device_complete(data)
    
    def add_latency_record(self, data: Dict) -> bool:
        return self.add_latency_to_history(data)

    def list_available_tables(self) -> List[str]:
        return ["devices", "device_history", "latency_history", "alerts"]

    def get_status_info(self) -> Dict:
        return {"status": "enabled" if self.enabled else "disabled", "last_sync": str(self.last_sync_time)}
