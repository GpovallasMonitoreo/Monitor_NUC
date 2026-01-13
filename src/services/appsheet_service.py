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
    Servicio AppSheet API v2 - VERSIÓN ARGOS BLINDADA
    Maneja respuestas vacías (200 OK Empty Body) y exige Selectores en lecturas.
    """
    
    def __init__(self):
        # 1. Limpieza de Credenciales (.strip() elimina espacios invisibles)
        raw_key = os.getenv('APPSHEET_API_KEY', '')
        raw_id = os.getenv('APPSHEET_APP_ID', '')
        
        self.api_key = raw_key.strip() if raw_key else ''
        self.app_id = raw_id.strip() if raw_id else ''
        self.base_url = "https://api.appsheet.com/api/v2"
        
        env_enabled = os.getenv('APPSHEET_ENABLED', 'false').lower()
        is_config_enabled = env_enabled in ['true', '1', 'yes', 'on']
        has_creds = len(self.api_key) > 5 and len(self.app_id) > 5 and 'tu_api_key' not in self.api_key

        if not is_config_enabled or not has_creds:
            self.enabled = False
            logger.warning(f"⚠️ AppSheetService OFF - Credenciales inválidas o deshabilitado.")
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService Listo - AppID: {self.app_id[:8]}...")

    def _make_appsheet_request(self, table: str, action: str, rows: List[Dict] = None, properties: Dict = None) -> Optional[Any]:
        """Envía petición HTTP manejando respuestas vacías de AppSheet"""
        try:
            if not self.enabled: return None
            
            # Construcción de Propiedades
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
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            # Timeout extendido a 45s por latencia de AppSheet
            response = requests.post(url, headers=self.headers, json=payload, timeout=45)
            
            # --- CORRECCIÓN PRINCIPAL: MANEJO DE RESPUESTA ---
            if response.status_code == 200:
                self.last_sync_time = datetime.now(TZ_MX)
                
                # Caso raro: 200 OK pero cuerpo vacío (Sucede con 'Find' sin resultados)
                if not response.text or not response.text.strip():
                    # Si era una búsqueda (Find), retornamos lista vacía. Si era Add, éxito genérico.
                    return [] if action == "Find" else {"status": "success (empty body)"}
                
                try:
                    return response.json()
                except json.JSONDecodeError:
                    # Si es texto plano pero 200 OK
                    logger.warning(f"⚠️ AppSheet devolvió 200 OK pero no JSON: {response.text[:100]}")
                    return {"status": "ok", "raw": response.text}
            
            # Errores HTTP
            logger.error(f"❌ AppSheet Error {response.status_code} en '{table}': {response.text}")
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
    # ESCRITURA (WRITE)
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
            # Limpieza de Nulos -> Strings vacíos
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
    # LECTURA (READ) - CORREGIDO PARA INCLUIR SELECTORES
    # ==========================================================
    def get_full_history(self, limit: int = 100) -> List[Dict]:
        """Obtiene historial reciente. IMPORTANTE: Selector genérico"""
        try:
            if not self.enabled: return []
            # Selector "true" es necesario para que 'Find' devuelva algo
            selector = f"Filter(device_history, true)"
            result = self._make_appsheet_request(
                "device_history", 
                "Find", 
                properties={"Selector": selector, "Top": limit}
            )
            
            # Normalización de respuesta
            if isinstance(result, list): return result
            if isinstance(result, dict): return result.get('Rows', [])
            return []
        except Exception: return []

    def get_history_for_device(self, pc_name: str) -> List[Dict]:
        try:
            if not self.enabled: return []
            selector = f"Filter(device_history, [pc_name] = '{pc_name}')"
            result = self._make_appsheet_request(
                "device_history", 
                "Find", 
                properties={"Selector": selector}
            )
            
            if isinstance(result, list): return result
            if isinstance(result, dict): return result.get('Rows', [])
            return []
        except Exception: return []

    # ==========================================================
    # DIAGNÓSTICO
    # ==========================================================
    def _test_table_connection(self, table_name: str) -> bool:
        """Prueba de conexión con Selector explícito"""
        try:
            # Sin selector, 'Find' puede devolver body vacío y causar error.
            selector = f"Filter({table_name}, true)"
            res = self._make_appsheet_request(
                table_name, 
                "Find", 
                properties={"Selector": selector, "Top": 1}
            )
            # Si res es [] (lista vacía), la conexión es ÉXITO, solo que no hay datos.
            return res is not None
        except:
            return False

    def test_history_connection(self) -> bool:
        return self._test_table_connection("device_history")

    def get_status_info(self) -> Dict:
        return {"status": "enabled", "app_id_len": len(self.app_id)}
        
    def get_system_stats(self) -> Dict:
        return {"status": "ok", "mode": "DB-Native"}
    
    # Compatibilidad
    def sync_device_complete(self, data: Dict) -> bool: return self.get_or_create_device(data)[0]
    def upsert_device(self, data: Dict) -> bool: return self.get_or_create_device(data)[0]
    def add_latency_record(self, data: Dict) -> bool: return self.add_latency_to_history(data)
    def list_available_tables(self) -> List[str]: return ["devices", "device_history", "latency_history", "alerts"]
