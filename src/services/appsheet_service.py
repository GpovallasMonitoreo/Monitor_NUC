import os
import requests
import json
import hashlib
import uuid
from datetime import datetime, timedelta
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
    Servicio AppSheet API v2 - VERSIÓN ARGOS DEBUG
    Incluye limpieza de credenciales y manejo seguro de errores JSON.
    """
    
    def __init__(self):
        # --- CORRECCIÓN CRÍTICA: .strip() ---
        # Render a veces agrega espacios invisibles o saltos de línea al copiar/pegar
        raw_key = os.getenv('APPSHEET_API_KEY', '')
        raw_id = os.getenv('APPSHEET_APP_ID', '')
        
        self.api_key = raw_key.strip() if raw_key else ''
        self.app_id = raw_id.strip() if raw_id else ''
        
        self.base_url = "https://api.appsheet.com/api/v2"
        
        env_enabled = os.getenv('APPSHEET_ENABLED', 'false').lower()
        is_config_enabled = env_enabled in ['true', '1', 'yes', 'on']
        
        # Validación de credenciales
        has_creds = len(self.api_key) > 5 and len(self.app_id) > 5 and 'tu_api_key' not in self.api_key

        if not is_config_enabled or not has_creds:
            self.enabled = False
            # Logueamos por qué falló (sin mostrar la key completa)
            logger.warning(f"⚠️ AppSheetService OFF - Config: {is_config_enabled}, Creds: {has_creds}")
            logger.warning(f"   AppID Length: {len(self.app_id)}")
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService Listo - AppID: {self.app_id[:8]}... (Longitud: {len(self.app_id)})")

    def _make_appsheet_request(self, table: str, action: str, rows: List[Dict] = None, properties: Dict = None) -> Optional[Any]:
        """Envía petición HTTP a la API con DEBUG EXTENDIDO"""
        try:
            if not self.enabled: return None
            
            # 1. Construir URL y Payload
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            props = {
                "Locale": "es-MX",
                "Timezone": "Central Standard Time"
            }
            if properties: props.update(properties)

            payload = {
                "Action": action, 
                "Properties": props
            }
            if rows: payload["Rows"] = rows
            
            # 2. Enviar Request
            # logger.info(f"📡 Enviando a {url}...") # Descomentar solo si es necesario debuggear URL
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            # 3. MANEJO DE RESPUESTA (AQUÍ OCURRE EL ERROR ACTUALMENTE)
            try:
                # Intentamos decodificar JSON
                response_data = response.json()
                
                if response.status_code == 200:
                    self.last_sync_time = datetime.now(TZ_MX)
                    return response_data
                else:
                    logger.error(f"❌ AppSheet Error {response.status_code}: {json.dumps(response_data)}")
                    return None
                    
            except json.JSONDecodeError:
                # --- AQUÍ CAPTURAMOS EL ERROR 'Expecting value...' ---
                logger.error(f"🔥 ERROR DE FORMATO: AppSheet no devolvió JSON.")
                logger.error(f"   Status Code: {response.status_code}")
                logger.error(f"   URL Usada: {url}")
                logger.error(f"   Respuesta CRUDA recibida: {response.text[:500]}") # Imprime los primeros 500 chars
                return None
            
        except Exception as e:
            logger.error(f"🔥 Error conexión crítica: {e}")
            return None

    def generate_device_id(self, pc_name: str) -> str:
        try:
            if not pc_name: return "UNKNOWN"
            clean_name = pc_name.strip().upper()
            if clean_name.startswith("MX_") and len(clean_name.split(' ')[0]) > 3:
                return clean_name.split(' ')[0].strip()
            return f"HASH_{hashlib.md5(clean_name.encode()).hexdigest()[:12].upper()}"
        except: return "ERROR_ID"

    # ==========================================================
    # MÉTODOS DE ESCRITURA
    # ==========================================================
    def get_or_create_device(self, device_data: Dict) -> tuple:
        try:
            if not self.enabled: return False, None, False
            pc_name = device_data.get('pc_name', '').strip()
            if not pc_name: return False, None, False
            
            device_id = self.generate_device_id(pc_name)
            current_time = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            device_row = {
                "device_id": device_id,
                "pc_name": pc_name,
                "unit": str(device_data.get('unit', 'General')),
                "public_ip": str(device_data.get('public_ip', device_data.get('ip', ''))),
                "last_known_location": str(device_data.get('locName', pc_name)),
                "updated_at": current_time
            }
            device_row = {k: (v if v is not None else "") for k, v in device_row.items()}
            
            result = self._make_appsheet_request("devices", "Add", [device_row])
            return (result is not None), device_id, True
        except Exception as e:
            logger.error(f"Error get_or_create_device: {e}")
            return False, None, False

    def add_history_entry(self, log_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            dev_name = log_data.get('device_name') or log_data.get('pc_name')
            if not dev_name: return False

            # Intentar asegurar padre
            self.get_or_create_device({
                "pc_name": dev_name,
                "unit": log_data.get('unit', 'General')
            })

            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            row = {
                "device_name": str(dev_name),
                "pc_name": str(dev_name),
                "exec": str(log_data.get('exec', '')),
                "action": str(log_data.get('action', 'Info')),
                "what": str(log_data.get('what', 'General')),
                "desc": str(log_data.get('desc', '')),
                "solved": str(log_data.get('solved', 'true')),
                "locName": str(log_data.get('locName', dev_name)),
                "unit": str(log_data.get('unit', 'General')),
                "status_snapshot": str(log_data.get('status_snapshot', 'active')),
                "timestamp": ts
            }
            
            logger.info(f"📝 Enviando Bitácora: {dev_name}")
            result = self._make_appsheet_request("device_history", "Add", [row])
            return result is not None
        except Exception as e:
            logger.error(f"Error add_history_entry: {e}")
            return False

    def add_latency_to_history(self, device_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            pc_name = device_data.get('pc_name', '')
            if not pc_name: return False
            
            device_id = self.generate_device_id(pc_name)
            record_id = str(uuid.uuid4())
            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            row = {
                "record_id": record_id,
                "device_id": device_id,
                "timestamp": ts,
                "latency_ms": str(device_data.get('latency', 0)), 
                "cpu_load": str(device_data.get('cpu_load_percent', 0)),
                "ram_usage": str(device_data.get('ram_percent', 0)),
                "temp_c": str(device_data.get('temperature', 0)),
                "disk_usage": str(device_data.get('disk_percent', 0)),
                "status": str(device_data.get('status', 'online')),
                "extended_sensors": str(device_data.get('extended_sensors', ''))[:2000]
            }
            # Verificar nombre exacto de la tabla (Case Sensitive)
            result = self._make_appsheet_request("latency_history", "Add", [row])
            return result is not None
        except Exception: return False

    def add_alert(self, data: Dict, type_alert: str, msg: str, sev: str) -> bool:
        try:
            if not self.enabled: return False
            pc_name = data.get('pc_name', '')
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
                "resolved_at": ""
            }
            result = self._make_appsheet_request("alerts", "Add", [row])
            return result is not None
        except Exception: return False

    # ==========================================================
    # MÉTODOS DE LECTURA (NECESARIOS PARA API.PY)
    # ==========================================================
    def get_full_history(self, limit: int = 100) -> List[Dict]:
        try:
            if not self.enabled: return []
            result = self._make_appsheet_request("device_history", "Find", properties={"Top": limit})
            if not result: return []
            return result if isinstance(result, list) else result.get('Rows', [])
        except Exception: return []

    def get_history_for_device(self, pc_name: str) -> List[Dict]:
        try:
            if not self.enabled: return []
            selector = f"Filter(device_history, [pc_name] = '{pc_name}')"
            result = self._make_appsheet_request("device_history", "Find", properties={"Selector": selector})
            return result if isinstance(result, list) else result.get('Rows', [])
        except Exception: return []

    # ==========================================================
    # MÉTODOS DE DIAGNÓSTICO
    # ==========================================================
    def _test_table_connection(self, table_name: str) -> bool:
        try:
            res = self._make_appsheet_request(table_name, "Find", properties={"Top": 1})
            return res is not None
        except: return False

    def test_history_connection(self) -> bool:
        return self._test_table_connection("device_history")

    def get_status_info(self) -> Dict:
        return {"status": "enabled", "app_id_len": len(self.app_id)}

    def get_system_stats(self) -> Dict:
        return {"status": "ok"}
    
    # Compatibilidad
    def sync_device_complete(self, data: Dict) -> bool: return self.get_or_create_device(data)[0]
    def upsert_device(self, data: Dict) -> bool: return self.get_or_create_device(data)[0]
    def add_latency_record(self, data: Dict) -> bool: return self.add_latency_to_history(data)
    def list_available_tables(self) -> List[str]: return ["devices", "device_history", "latency_history", "alerts"]
