import os
import requests
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

# Configuración de Zona Horaria
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
    
    # --- MÉTODOS AUXILIARES ---
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
            payload = {"Action": action, "Properties": {"Locale": "en-US"}}
            if rows: payload["Rows"] = rows
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action",
                headers=self.headers, json=payload, timeout=20
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"AppSheet request error: {e}")
            return None

    # --- MÉTODOS CORE (LATENCIA Y DISPOSITIVOS) ---

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
                "updated_at": datetime.now(TZ_MX).isoformat()
            }
            self._make_safe_request("devices", "Add", [row]) 
            self.last_sync_time = datetime.now(TZ_MX)
            return True
        except: return False

    def add_latency_record(self, device_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(device_data['pc_name'])
            
            def get_temp(d):
                try:
                    if d.get('temperature'): return float(d['temperature'])
                    if d.get('extended_sensors') and 'Intel CPU' in d['extended_sensors']:
                        for s in d['extended_sensors']['Intel CPU']:
                            if s['tipo'] == 'Temperature': return float(s['valor'])
                except: pass
                return 0.0

            row = {
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).isoformat(),
                "latency_ms": float(device_data.get('latency', 0)),
                "cpu_percent": float(device_data.get('cpu_load_percent', 0)),
                "ram_percent": float(device_data.get('ram_percent', 0)),
                "temperature_c": get_temp(device_data),
                "status": str(device_data.get('status', 'online'))
            }
            self._make_safe_request("latency_history", "Add", [row])
            return True
        except: return False

    def add_alert(self, device_data: Dict, alert_type: str, message: str, severity: str = "medium") -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(device_data['pc_name'])
            row = {
                "device_id": device_id,
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "timestamp": datetime.now(TZ_MX).isoformat(),
                "resolved": False,
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
            
            # 1. Total Dispositivos
            devs = self._make_safe_request("devices", "Find", [])
            total_devs = len(devs) if isinstance(devs, list) else 0
            
            # 2. Historial Latencia
            lat_data = self._make_safe_request("latency_history", "Get") or []
            if not isinstance(lat_data, list): lat_data = []
            
            stats = {'avg_latency': 0, 'avg_cpu': 0, 'total_records': 0, 'total_devices': total_devs, 'uptime_percent': 0, 'last_sync': None}
            
            if lat_data:
                lats = [float(r['latency_ms']) for r in lat_data if r.get('latency_ms')]
                if lats: stats['avg_latency'] = round(sum(lats)/len(lats), 2)
                stats['total_records'] = len(lat_data)
                
            if self.last_sync_time: stats['last_sync'] = self.last_sync_time.isoformat()
            return stats
        except: return {'avg_latency': 0, 'total_devices': 0}

    # ==========================================
    # MÉTODOS DE BITÁCORA Y FICHAS (CORREGIDOS)
    # ==========================================

    def add_history_entry(self, log_data: Dict) -> bool:
        """
        Guarda ficha en device_history y actualiza status en devices.
        """
        try:
            if not self.enabled: return False
            
            # Asegurar ID correcto
            device_id = self.generate_device_id(log_data.get('device_name', ''))
            
            history_row = {
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).isoformat(),
                "requester": log_data.get('req', 'Sistema'),
                "executor": log_data.get('exec', 'Pendiente'),
                "action_type": log_data.get('action', 'Mantenimiento'),
                "component": log_data.get('what', '-'),
                "description": log_data.get('desc', ''),
                "is_resolved": str(log_data.get('solved', False)).lower(),
                "location_snapshot": log_data.get('locName', ''),
                "unit_snapshot": log_data.get('unit', 'General'),
                "status_snapshot": log_data.get('status_snapshot', 'active')
            }
            
            logger.info(f"💾 Guardando Ficha: {history_row}")
            
            # 1. Guardar en Historial
            res_hist = self._make_safe_request("device_history", "Add", [history_row])
            
            # 2. Si es una BAJA o REACTIVACIÓN, actualizar tabla maestra de devices
            action = log_data.get('action', '')
            if action == 'Baja':
                self.update_device_status(device_id, 'offline')
            
            return res_hist is not None
            
        except Exception as e:
            logger.error(f"Error add_history_entry: {e}")
            return False

    def update_device_status(self, device_id: str, status: str):
        """Helper para cambiar estado en tabla maestra"""
        try:
            row = {"device_id": device_id, "status": status, "updated_at": datetime.now(TZ_MX).isoformat()}
            self._make_safe_request("devices", "Edit", [row])
        except: pass

    def get_full_history(self) -> List[Dict]:
        """Obtiene bitácora completa"""
        try:
            if not self.enabled: return []
            data = self._make_safe_request("device_history", "Find", [])
            if isinstance(data, list):
                return sorted(data, key=lambda x: x.get('timestamp', ''), reverse=True)
            return []
        except: return []
