import os
import requests
import json
import hashlib
import uuid  # <--- NUEVO: Para generar IDs únicos (alert_id, history_id)
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
    """Servicio para interactuar con AppSheet Database"""
    
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY', '')
        self.app_id = os.getenv('APPSHEET_APP_ID', '')
        self.base_url = os.getenv('APPSHEET_BASE_URL', 'https://api.appsheet.com/api/v2')
        
        env_enabled = os.getenv('APPSHEET_ENABLED', 'false').lower()
        is_config_enabled = env_enabled in ['true', '1', 'yes', 'on']
        has_creds = self.api_key and self.app_id and 'tu_api_key' not in self.api_key

        if not is_config_enabled or not has_creds:
            self.enabled = False
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService Conectado")

        try:
            self._test_table_connection('devices')
        except: pass
    
    def _test_table_connection(self, table_name: str) -> bool:
        try:
            if not self.enabled: return False
            payload = {"Action": "Find", "Properties": {"Locale": "en-US", "Top": 1}}
            requests.post(f"{self.base_url}/apps/{self.app_id}/tables/{table_name}/Action", headers=self.headers, json=payload, timeout=5)
            return True
        except: return False

    def generate_device_id(self, pc_name: str) -> str:
        try:
            if pc_name and pc_name.strip().upper().startswith("MX_"):
                parts = pc_name.strip().split(' ')
                if len(parts) > 0 and len(parts[0]) > 5: return parts[0].strip()
            return hashlib.md5(pc_name.encode()).hexdigest()[:16].upper()
        except: return "UNKNOWN_ID"

    def _make_safe_request(self, table: str, action: str, rows: List[Dict] = None) -> Optional[Any]:
        try:
            if not self.enabled: return None
            
            payload = {"Action": action, "Properties": {"Locale": "es-MX", "Timezone": "Central Standard Time"}}
            if rows: payload["Rows"] = rows
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action",
                headers=self.headers, json=payload, timeout=20
            )
            
            if response.status_code == 200:
                try: return response.json()
                except: return {"success": True}
            
            logger.error(f"AppSheet Error {response.status_code} en '{table}': {response.text}")
            return None
        except Exception as e:
            logger.error(f"AppSheet request error: {e}")
            return None

    # --- MÉTODOS DE DISPOSITIVOS Y LATENCIA ---

    def upsert_device(self, device_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(device_data['pc_name'])
            
            row = {
                "device_id": device_id,
                "pc_name": device_data['pc_name'],
                "unit": device_data.get('unit', 'General'),
                "public_ip": device_data.get('public_ip', device_data.get('ip', '')),
                "status": device_data.get('status', 'online'),
                "updated_at": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            }
            self._make_safe_request("devices", "Add", [row]) 
            self.last_sync_time = datetime.now(TZ_MX)
            return True
        except: return False

    def add_latency_record(self, device_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Generamos un ID único para cada registro de latencia también (Buena práctica)
            record_id = str(uuid.uuid4())

            def get_temp(d):
                try:
                    if d.get('temperature'): return float(d['temperature'])
                    if d.get('extended_sensors') and 'Intel CPU' in d['extended_sensors']:
                        for s in d['extended_sensors']['Intel CPU']:
                            if s['tipo'] == 'Temperature': return float(s['valor'])
                except: pass
                return 0.0

            row = {
                "record_id": record_id, # Asegúrate de tener esta columna o quitarla si usas RowNumber
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "latency_ms": float(device_data.get('latency', 0)),
                "cpu_percent": float(device_data.get('cpu_load_percent', 0)),
                "ram_percent": float(device_data.get('ram_percent', 0)),
                "temperature_c": get_temp(device_data),
                "status": str(device_data.get('status', 'online'))
            }
            # Si tu tabla latency_history no tiene record_id, comenta la línea de arriba
            # Pero para alerts y history ES OBLIGATORIO.
            
            self._make_safe_request("latency_history", "Add", [row])
            return True
        except: return False

    def add_alert(self, device_data: Dict, alert_type: str, message: str, severity: str = "medium") -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # --- CORRECCIÓN: Generar alert_id ---
            alert_id = str(uuid.uuid4())
            
            row = {
                "alert_id": alert_id,  # <--- CAMPO FALTANTE AGREGADO
                "device_id": device_id,
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "resolved": "NO",
                "pc_name": device_data.get('pc_name', 'Unknown')
            }
            self._make_safe_request("alerts", "Add", [row])
            return True
        except: return False

    def get_status_info(self) -> Dict[str, Any]:
        connection_ok = self._test_table_connection('devices')
        return {
            "status": "enabled" if self.enabled else "disabled",
            "available": connection_ok,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None
        }

    def get_system_stats(self, days: int = 1) -> Dict[str, Any]:
        try:
            if not self.enabled: return {'avg_latency': 0, 'total_devices': 0}
            lat_data = self._make_safe_request("latency_history", "Get") or []
            if not isinstance(lat_data, list): lat_data = []
            devs = self._make_safe_request("devices", "Find", [])
            total_devs = len(devs) if isinstance(devs, list) else 0
            stats = {'avg_latency': 0, 'avg_cpu': 0, 'total_records': 0, 'total_devices': total_devs, 'uptime_percent': 0, 'last_sync': None}
            if lat_data:
                lats = [float(r['latency_ms']) for r in lat_data if r.get('latency_ms')]
                if lats: stats['avg_latency'] = round(sum(lats)/len(lats), 2)
                stats['total_records'] = len(lat_data)
            if self.last_sync_time: stats['last_sync'] = self.last_sync_time.isoformat()
            return stats
        except: return {'avg_latency': 0, 'total_devices': 0}

    # --- MÉTODOS DE BITÁCORA ---

    def add_history_entry(self, log_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            
            device_name = log_data.get('device_name') or log_data.get('pc_name')
            if not device_name: return False

            # Asegurar dispositivo padre
            self.upsert_device({
                "pc_name": device_name,
                "unit": log_data.get('unit', 'General'),
                "status": 'online'
            })
            
            device_id = self.generate_device_id(device_name)
            
            # --- CORRECCIÓN: Generar history_id ---
            history_id = str(uuid.uuid4())

            history_row = {
                "history_id": history_id, # <--- ID ÚNICO PARA LA FICHA
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "requester": log_data.get('req', 'Sistema'),
                "executor": log_data.get('exec', 'Pendiente'),
                "action_type": log_data.get('action', 'Mantenimiento'),
                "component": log_data.get('what', '-'),
                "description": log_data.get('desc', ''),
                "is_resolved": "YES" if log_data.get('solved') else "NO",
                "location_snapshot": log_data.get('locName', ''),
                "unit_snapshot": log_data.get('unit', 'General'),
                "status_snapshot": log_data.get('status_snapshot', 'active')
            }
            
            logger.info(f"💾 Guardando Ficha {history_id}...")
            
            res_hist = self._make_safe_request("device_history", "Add", [history_row])
            
            action = log_data.get('action', '')
            if action == 'Baja': self.update_device_status(device_id, 'offline')
            elif action in ['Instalación', 'Renovación']: self.update_device_status(device_id, 'online')
            
            return res_hist is not None
            
        except Exception as e:
            logger.error(f"Error add_history_entry: {e}")
            return False

    def update_device_status(self, device_id: str, status: str):
        try:
            row = {"device_id": device_id, "status": status, "updated_at": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')}
            self._make_safe_request("devices", "Edit", [row])
        except: pass

    def get_full_history(self) -> List[Dict]:
        try:
            if not self.enabled: return []
            data = self._make_safe_request("device_history", "Find", [])
            if isinstance(data, list):
                return sorted(data, key=lambda x: x.get('timestamp', ''), reverse=True)
            return []
        except: return []
