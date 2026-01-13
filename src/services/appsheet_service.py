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
    Servicio AppSheet API v2 - VERSIÓN ARGOS FULL STACK
    Soporta Escritura (Add), Lectura (Find) y Diagnóstico.
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
        logger.info(f"✅ AppSheetService Listo - App: {self.app_id[:8]}...")

    def _make_appsheet_request(self, table: str, action: str, rows: List[Dict] = None, properties: Dict = None) -> Optional[Any]:
        """Envía petición HTTP a la API (Soporta Add y Find)"""
        try:
            if not self.enabled: return None
            
            # Propiedades base
            props = {
                "Locale": "es-MX",
                "Timezone": "Central Standard Time"
            }
            # Fusionar propiedades extra (ej: Selectores, Top)
            if properties:
                props.update(properties)

            payload = {
                "Action": action, 
                "Properties": props
            }
            if rows: payload["Rows"] = rows
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                self.last_sync_time = datetime.now(TZ_MX)
                return response.json()
            
            logger.error(f"❌ AppSheet Error {response.status_code} en tabla '{table}': {response.text}")
            return None
            
        except Exception as e:
            logger.error(f"🔥 Error crítico conexión AppSheet: {e}")
            return None

    def generate_device_id(self, pc_name: str) -> str:
        """Genera ID Hash MD5 consistente"""
        try:
            if not pc_name: return "UNKNOWN"
            clean_name = pc_name.strip().upper()
            if clean_name.startswith("MX_") and len(clean_name.split(' ')[0]) > 3:
                return clean_name.split(' ')[0].strip()
            return f"HASH_{hashlib.md5(clean_name.encode()).hexdigest()[:12].upper()}"
        except: return "ERROR_ID"

    # ==========================================================
    # 1. ESCRITURA (WRITE METHODS)
    # ==========================================================

    def get_or_create_device(self, device_data: Dict) -> tuple:
        """Sincroniza con la tabla 'devices'."""
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
        """Inserta en 'device_history'."""
        try:
            if not self.enabled: return False
            dev_name = log_data.get('device_name') or log_data.get('pc_name')
            if not dev_name: return False

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
            result = self._make_appsheet_request("device_history", "Add", [row])
            return result is not None
        except Exception as e:
            logger.error(f"Error add_history_entry: {e}")
            return False

    def add_latency_to_history(self, device_data: Dict) -> bool:
        """Inserta en 'latency_history'."""
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
            result = self._make_appsheet_request("latency_history", "Add", [row])
            return result is not None
        except Exception: return False

    def add_alert(self, data: Dict, type_alert: str, msg: str, sev: str) -> bool:
        """Inserta en 'alerts'."""
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
                "resolved_at": ""
            }
            result = self._make_appsheet_request("alerts", "Add", [row])
            return result is not None
        except Exception: return False

    # ==========================================================
    # 2. LECTURA (READ METHODS) - REQUERIDOS POR API.PY
    # ==========================================================

    def get_full_history(self, limit: int = 100) -> List[Dict]:
        """Obtiene historial reciente (Para /history/all)"""
        try:
            if not self.enabled: return []
            
            # Action: Find para leer datos
            # OJO: AppSheet retorna una lista de filas directamente o dentro de un objeto
            result = self._make_appsheet_request(
                "device_history", 
                "Find", 
                properties={"Selector": "Filter(device_history, true)", "Top": limit} # Selector simple
            )
            
            if not result: return []
            
            # Normalizar respuesta (A veces es lista directa, a veces dict)
            rows = result if isinstance(result, list) else result.get('Rows', [])
            return rows
        except Exception as e:
            logger.error(f"Error leyendo historial: {e}")
            return []

    def get_history_for_device(self, pc_name: str) -> List[Dict]:
        """Obtiene historial filtrado por dispositivo"""
        try:
            if not self.enabled: return []
            
            # Selector AppSheet: [pc_name] = 'VALOR'
            selector = f"Filter(device_history, [pc_name] = '{pc_name}')"
            
            result = self._make_appsheet_request(
                "device_history", 
                "Find", 
                properties={"Selector": selector}
            )
            
            rows = result if isinstance(result, list) else result.get('Rows', [])
            return rows
        except Exception as e:
            logger.error(f"Error historial dispositivo: {e}")
            return []

    # ==========================================================
    # 3. DIAGNÓSTICO Y COMPATIBILIDAD (REQUERIDOS POR APP.PY)
    # ==========================================================

    def _test_table_connection(self, table_name: str) -> bool:
        """Prueba simple para ver si la tabla responde (Para app.py)"""
        try:
            # Intentamos leer 1 fila cualquiera
            res = self._make_appsheet_request(table_name, "Find", properties={"Top": 1})
            return res is not None
        except:
            return False

    def test_history_connection(self) -> bool:
        """Alias específico para device_history"""
        return self._test_table_connection("device_history")

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
        return {
            "status": "enabled" if self.enabled else "disabled", 
            "last_sync": str(self.last_sync_time),
            "app_id": self.app_id
        }
        
    def get_system_stats(self) -> Dict:
        return {"status": "ok", "mode": "DB-Native"}
