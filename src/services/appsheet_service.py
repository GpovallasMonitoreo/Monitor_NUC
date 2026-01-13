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
    Servicio AppSheet "Blindado".
    - Maneja respuestas 200 vacías como éxito.
    - Convierte todo a Texto antes de enviar.
    - Limpia credenciales de espacios invisibles.
    """
    
    def __init__(self):
        # 1. Limpieza de credenciales (Render suele meter espacios al final)
        raw_key = os.getenv('APPSHEET_API_KEY', '')
        raw_id = os.getenv('APPSHEET_APP_ID', '')
        
        self.api_key = raw_key.strip()
        self.app_id = raw_id.strip()
        self.base_url = "https://api.appsheet.com/api/v2"
        
        # 2. Validación de Estado
        env_enabled = os.getenv('APPSHEET_ENABLED', 'false').lower()
        is_config_enabled = env_enabled in ['true', '1', 'yes', 'on']
        has_creds = len(self.api_key) > 5 and len(self.app_id) > 5

        if not is_config_enabled or not has_creds:
            self.enabled = False
            logger.warning("⚠️ AppSheetService Apagado (Credenciales faltantes o flag off)")
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService Inicializado - App: ...{self.app_id[-4:]}")

    def _make_safe_request(self, table: str, action: str, rows: List[Dict] = None, properties: Dict = None) -> Optional[Any]:
        """Envía petición HTTP y maneja el error de 'JSON Vacío'."""
        try:
            if not self.enabled: return None
            
            final_props = {"Locale": "es-MX", "Timezone": "Central Standard Time"}
            if properties: final_props.update(properties)

            payload = {"Action": action, "Properties": final_props}
            if rows: payload["Rows"] = rows
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            # Timeout 30s
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                self.last_sync_time = datetime.now(TZ_MX)
                
                # ÉXITO SILENCIOSO: Si responde 200 pero sin texto, asumimos OK.
                if not response.text or len(response.text.strip()) == 0:
                    return {"status": "success", "empty_response": True}
                
                try:
                    return response.json()
                except json.JSONDecodeError:
                    # ÉXITO RARO: Responde 200 pero texto plano.
                    return {"status": "success", "raw": response.text}
            
            logger.error(f"❌ Error AppSheet {response.status_code} en {table}: {response.text}")
            return None
            
        except Exception as e:
            logger.error(f"🔥 Excepción conectando a AppSheet: {e}")
            return None

    def generate_device_id(self, pc_name: str) -> str:
        """Genera ID consistente."""
        try:
            if not pc_name: return "UNKNOWN"
            clean = pc_name.strip().upper()
            if clean.startswith("MX_") and len(clean) > 4:
                 return clean.split(' ')[0].strip()
            return f"HASH_{hashlib.md5(clean.encode()).hexdigest()[:10].upper()}"
        except: return "ERROR_ID"

    # --- MÉTODOS DE ESCRITURA (TODO A STRING) ---

    def get_or_create_device(self, device_data: Dict) -> tuple:
        try:
            if not self.enabled: return False, None, False
            pc_name = str(device_data.get('pc_name', '')).strip()
            if not pc_name: return False, None, False
            
            device_id = self.generate_device_id(pc_name)
            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            row = {
                "device_id": device_id,
                "pc_name": pc_name,
                "unit": str(device_data.get('unit', 'General')),
                "public_ip": str(device_data.get('public_ip', device_data.get('ip', ''))),
                "last_known_location": str(device_data.get('locName', pc_name)),
                "updated_at": ts
            }
            res = self._make_safe_request("devices", "Add", [row])
            return (res is not None), device_id, True
        except: return False, None, False

    def add_history_entry(self, log_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            pc_name = log_data.get('pc_name') or log_data.get('device_name')
            if not pc_name: return False

            # Asegurar Padre
            success, device_id, _ = self.get_or_create_device({"pc_name": pc_name, "unit": log_data.get('unit')})
            if not success: device_id = self.generate_device_id(pc_name)

            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            row = {
                "history_id": str(uuid.uuid4()),
                "device_id": device_id, # Link al ID, no al nombre
                "action": str(log_data.get('action', 'Info')),
                "what": str(log_data.get('what', 'General')),
                "desc": str(log_data.get('desc', 'NA')),
                "exec": str(log_data.get('exec', 'Sistema')),
                "solved": str(log_data.get('solved', 'true')).lower(), # "true" string
                "unit": str(log_data.get('unit', 'General')),
                "timestamp": ts
            }
            
            res = self._make_safe_request("device_history", "Add", [row])
            return res is not None
        except Exception as e:
            logger.error(f"Error add_history: {e}")
            return False

    def add_latency_to_history(self, data: Dict) -> bool:
        try:
            if not self.enabled: return False
            pc_name = data.get('pc_name', '')
            device_id = self.generate_device_id(pc_name)
            
            row = {
                "record_id": str(uuid.uuid4()),
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "latency_ms": str(data.get('latency', 0)),
                "cpu_load": str(data.get('cpu_load_percent', 0)),
                "ram_usage": str(data.get('ram_percent', 0)),
                "status": str(data.get('status', 'online'))
            }
            res = self._make_safe_request("latency_history", "Add", [row])
            return res is not None
        except: return False

    def add_alert(self, data: Dict, type_alert: str, msg: str, sev: str) -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(data.get('pc_name'))
            row = {
                "alert_id": str(uuid.uuid4()),
                "device_id": device_id,
                "alert_type": str(type_alert),
                "severity": str(sev),
                "message": str(msg),
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            }
            res = self._make_safe_request("alerts", "Add", [row])
            return res is not None
        except: return False

    # --- MÉTODOS DE LECTURA Y COMPATIBILIDAD ---

    def get_full_history(self, limit: int = 50) -> List[Dict]:
        try:
            if not self.enabled: return []
            res = self._make_safe_request("device_history", "Find", properties={"Top": limit})
            if res and isinstance(res, list): return res
            if res and isinstance(res, dict): return res.get('Rows', [])
            return []
        except: return []

    def get_history_for_device(self, pc_name: str) -> List[Dict]:
        try:
            if not self.enabled: return []
            dev_id = self.generate_device_id(pc_name)
            selector = f"Filter(device_history, [device_id] = '{dev_id}')"
            res = self._make_safe_request("device_history", "Find", properties={"Selector": selector})
            if res and isinstance(res, list): return res
            if res and isinstance(res, dict): return res.get('Rows', [])
            return []
        except: return []

    def get_status_info(self) -> Dict:
        return {"status": "enabled", "last_sync": str(self.last_sync_time)}

    def get_system_stats(self) -> Dict:
        return {"status": "ok", "mode": "DB-Native"}

    # Aliases
    def sync_device_complete(self, data: Dict) -> bool: return self.get_or_create_device(data)[0]
    def upsert_device(self, data: Dict) -> bool: return self.get_or_create_device(data)[0]
    def add_latency_record(self, data: Dict) -> bool: return self.add_latency_to_history(data)
    def list_available_tables(self) -> List[str]: return ["devices", "device_history", "latency_history", "alerts"]
