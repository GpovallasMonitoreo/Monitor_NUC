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

TZ_MX = ZoneInfo("America/Mexico_City")
logger = logging.getLogger(__name__)

class AppSheetService:
    """
    Servicio para AppSheet API v2 - VERSIÓN ARGOS DB-NATIVE
    Ajustado para tipos de datos estrictos (Booleanos reales y Fechas SQL)
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
            logger.warning("AppSheetService deshabilitado - Credenciales faltantes")
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
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                self.last_sync_time = datetime.now(TZ_MX)
                return response.json()
            
            # LOGGING DE ERROR 400
            logger.error(f"❌ AppSheet Error {response.status_code} en tabla '{table}':")
            # logger.error(f"   Payload intentado: {json.dumps(rows, default=str)}") # Descomentar para debug extremo
            try:
                error_detail = response.json()
                logger.error(f"   Detalle API: {json.dumps(error_detail, indent=2)}")
            except:
                logger.error(f"   Respuesta Raw: {response.text}")
            
            return None
            
        except Exception as e:
            logger.error(f"🔥 Error conexión AppSheet: {e}")
            return None

    def generate_device_id(self, pc_name: str) -> str:
        """Genera ID Hash MD5"""
        try:
            if not pc_name: return "UNKNOWN"
            clean_name = pc_name.strip().upper()
            if clean_name.startswith("MX_") and len(clean_name.split(' ')[0]) > 3:
                return clean_name.split(' ')[0].strip()
            return f"HASH_{hashlib.md5(clean_name.encode()).hexdigest()[:12].upper()}"
        except: return "ERROR_ID"

    # ==========================================================
    # 1. TABLA DEVICES (MAESTRA)
    # ==========================================================
    def get_or_create_device(self, device_data: Dict) -> tuple:
        try:
            if not self.enabled: return False, None, False
            
            pc_name = device_data.get('pc_name', '').strip()
            if not pc_name: return False, None, False
            
            device_id = self.generate_device_id(pc_name)
            
            # CORRECCIÓN 1: Booleanos Nativos (No Strings)
            status_val = device_data.get('status', 'online')
            is_active = True if status_val == 'online' else False 
            
            device_row = {
                "device_id": device_id,
                "pc_name": pc_name,
                "unit": device_data.get('unit', 'General'),
                "public_ip": device_data.get('public_ip', device_data.get('ip', '')),
                "is_active": is_active, # Envía true/false real
                "updated_at": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # logger.info(f"🔄 Sync Device {pc_name}...")
            result = self._make_appsheet_request("devices", "Add", [device_row])
            
            return (result is not None), device_id, True
                
        except Exception as e:
            logger.error(f"Error get_or_create_device: {e}")
            return False, None, False

    # ==========================================================
    # 2. TABLA HISTORY (BITÁCORA)
    # ==========================================================
    def add_history_entry(self, log_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            dev_name = log_data.get('device_name') or log_data.get('pc_name')
            if not dev_name: return False

            # PASO CRÍTICO: Intentar crear el padre primero
            success, device_id, _ = self.get_or_create_device({
                "pc_name": dev_name,
                "unit": log_data.get('unit', 'General'),
                "status": 'online'
            })
            
            # Si falla la creación del dispositivo, NO enviamos historia (evita error 400 por Foreign Key)
            if not success:
                logger.warning(f"⚠️ Abortando bitácora para {dev_name}: No se pudo sincronizar el dispositivo padre.")
                return False

            # Preparar Ficha
            history_id = str(uuid.uuid4())
            
            # CORRECCIÓN 2: Booleanos Nativos
            raw_solved = log_data.get('solved') or log_data.get('is_resolved')
            is_resolved = True if raw_solved else False
            
            row = {
                # "history_id": history_id, # <--- PRUEBA: Si falla, comenta esta línea (deja que la DB genere el ID)
                "history_id": history_id,
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "requester": str(log_data.get('req', 'Sistema')),
                "executor": str(log_data.get('exec', 'Sistema')),
                "action_type": str(log_data.get('action', 'Mantenimiento')),
                "component": str(log_data.get('what', 'General')),
                "description": str(log_data.get('desc', 'NA')),
                "is_resolved": is_resolved, # Envía true/false real
                "unit_snapshot": str(log_data.get('unit', 'General')),
                "location_snapshot": str(dev_name)
            }
            
            logger.info(f"📝 Enviando Bitácora: {dev_name} - {row['action_type']}")
            result = self._make_appsheet_request("device_history", "Add", [row])
            return result is not None

        except Exception as e:
            logger.error(f"Error add_history_entry: {e}")
            return False

    # ==========================================================
    # 3. TABLA LATENCY (HISTORIAL TÉCNICO)
    # ==========================================================
    def add_latency_to_history(self, device_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            pc_name = device_data.get('pc_name', '')
            if not pc_name: return False
            
            # Asegurar padre
            success, device_id, _ = self.get_or_create_device(device_data)
            if not success: return False

            record_id = str(uuid.uuid4())
            
            row = {
                "record_id": record_id,
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "latency_ms": str(device_data.get('latency', 0)), # AppSheet DB suele aceptar Strings para números, pero idealmente enviar int/float
                "cpu_percent": str(device_data.get('cpu_load_percent', 0)),
                "ram_percent": str(device_data.get('ram_percent', 0)),
                "temperature_c": str(device_data.get('temperature', 0)),
                "disk_percent": str(device_data.get('disk_percent', 0)),
                "status": device_data.get('status', 'online'),
                "extended_sensors": str(device_data.get('extended_sensors', ''))[:2000]
            }
            
            # logger.info(f"📊 Enviando Latencia {pc_name}")
            result = self._make_appsheet_request("Latency_history", "Add", [row])
            return result is not None
                
        except Exception:
            return False

    # --- Métodos de Compatibilidad y Lectura ---
    
    def sync_device_complete(self, data: Dict) -> bool:
        success, _, _ = self.get_or_create_device(data)
        return success
    
    def upsert_device(self, data: Dict) -> bool:
        return self.sync_device_complete(data)
    
    def add_latency_record(self, data: Dict) -> bool:
        return self.add_latency_to_history(data)

    def add_alert(self, data: Dict, type: str, msg: str, sev: str) -> bool:
        return self.add_history_entry({
            "device_name": data.get('pc_name'),
            "action": "ALERTA",
            "what": type,
            "desc": f"[{sev.upper()}] {msg}",
            "req": "Watchdog",
            "solved": False,
            "unit": data.get('unit', 'General')
        })

    def list_available_tables(self) -> List[str]:
        return ["devices", "device_history", "Latency_history", "alerts"]

    def get_status_info(self) -> Dict:
        return {"status": "enabled" if self.enabled else "disabled", "last_sync": str(self.last_sync_time)}
        
    def get_system_stats(self) -> Dict:
        return {"status": "ok"}

    def get_full_history(self, limit: int = 200) -> List[Dict]:
        return []

    def get_history_for_device(self, pc_name: str) -> List[Dict]:
        return []
