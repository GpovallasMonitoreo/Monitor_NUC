import os
import requests
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

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
            logger.info("ℹ️ AppSheet deshabilitado o sin credenciales")
            self.enabled = False
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService inicializado")

        try:
            self._test_table_connection('devices')
        except: pass
    
    def _test_table_connection(self, table_name: str) -> bool:
        try:
            if not self.enabled: return False
            payload = {"Action": "Find", "Properties": {"Locale": "en-US", "Top": 1}}
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/{table_name}/Action",
                headers=self.headers, json=payload, timeout=5
            )
            return response.status_code == 200
        except: return False
    
    def generate_device_id(self, pc_name: str) -> str:
        """
        Genera el ID. Si viene con formato de sitio (MX_...), usa la clave.
        """
        try:
            if pc_name and pc_name.strip().upper().startswith("MX_"):
                parts = pc_name.strip().split(' ')
                if len(parts) > 0:
                    clean_id = parts[0].strip()
                    if len(clean_id) > 5:
                        return clean_id
            return hashlib.md5(pc_name.encode()).hexdigest()[:16].upper()
        except Exception:
            return hashlib.md5(pc_name.encode()).hexdigest()[:16].upper()
    
    def _make_safe_request(self, table: str, action: str, rows: List[Dict] = None) -> Optional[Any]:
        try:
            if not self.enabled: return None
            payload = {"Action": action, "Properties": {"Locale": "en-US"}}
            if rows: payload["Rows"] = rows
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action",
                headers=self.headers, json=payload, timeout=15
            )
            
            if response.status_code == 200:
                try: return response.json()
                except: return {"success": True}
            return None
        except Exception as e:
            logger.error(f"AppSheet error {table}/{action}: {e}")
            return None

    def upsert_device(self, device_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(device_data['pc_name'])
            location = f"{device_data.get('lat','')},{device_data.get('lng','')}" if device_data.get('lat') else ""

            device_row = {
                "device_id": device_id,
                "pc_name": device_data['pc_name'],
                "unit": device_data.get('unit', 'General'),
                "public_ip": device_data.get('public_ip', device_data.get('ip', '')),
                "last_known_location": location,
                "is_active": device_data.get('status', 'online') != 'offline',
                "status": device_data.get('status', 'online'),
                "updated_at": datetime.now().isoformat()
            }
            # Add y Edit para asegurar
            self._make_safe_request("devices", "Add", [device_row])
            self._make_safe_request("devices", "Edit", [device_row])
            self.last_sync_time = datetime.now()
            return True
        except Exception: return False

    def add_latency_record(self, device_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(device_data['pc_name'])
            latency_row = {
                "device_id": device_id,
                "timestamp": datetime.now().isoformat(),
                "latency_ms": float(device_data.get('latency', 0)),
                "cpu_percent": float(device_data.get('cpu_load_percent', 0)),
                "ram_percent": float(device_data.get('ram_percent', 0)),
                "temperature_c": float(device_data.get('temperature', 0)),
                "status": str(device_data.get('status', 'online'))
            }
            self._make_safe_request("latency_history", "Add", [latency_row])
            return True
        except Exception: return False

    def add_alert(self, device_data: Dict, alert_type: str, message: str, severity: str = "medium") -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(device_data['pc_name'])
            alert_row = {
                "device_id": device_id,
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "resolved": False,
                "pc_name": device_data.get('pc_name', 'Unknown')
            }
            self._make_safe_request("alerts", "Add", [alert_row])
            return True
        except Exception: return False
            
    def sync_device_complete(self, device_data: Dict):
        self.upsert_device(device_data)
        self.add_latency_record(device_data)

    def get_status_info(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "available": False, "message": "AppSheet deshabilitado"}
        
        connection_ok = self._test_table_connection('devices')
        return {
            "status": "enabled",
            "available": connection_ok,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "message": "Conectado" if connection_ok else "Error conexión",
            "app_id_preview": f"...{self.app_id[-4:]}" if self.app_id else "N/A"
        }

    def get_system_stats(self, days: int = 1) -> Dict[str, Any]:
        """Calcula estadísticas leyendo Devices (para el total) y Latency (para el historial)"""
        try:
            if not self.enabled: return self._get_default_stats()
            
            stats = self._get_default_stats()

            # 1. Obtener TOTAL de dispositivos registrados (Tabla devices)
            # Esto corrige el "--" en Dispositivos Sincronizados
            devices_response = self._make_safe_request("devices", "Find", []) # Find vacío trae todo
            if isinstance(devices_response, list):
                stats['total_devices'] = len(devices_response)
            
            # 2. Obtener historial reciente (Tabla latency_history)
            latency_data = self._make_safe_request("latency_history", "Get") or []
            if not isinstance(latency_data, list): latency_data = []
            
            if latency_data:
                latencies = []
                cpus = []
                online_count = 0
                
                # Filtrar solo registros de HOY para "Registros Hoy"
                today_str = datetime.now().strftime('%Y-%m-%d')
                records_today = 0

                for row in latency_data:
                    try:
                        # Contar registros de hoy
                        if row.get('timestamp') and str(row['timestamp']).startswith(today_str):
                            records_today += 1

                        if row.get('latency_ms'): latencies.append(float(row['latency_ms']))
                        if row.get('cpu_percent'): cpus.append(float(row['cpu_percent']))
                        if row.get('status') == 'online': online_count += 1
                    except: continue
                
                if latencies: stats['avg_latency'] = round(sum(latencies) / len(latencies), 2)
                if cpus: stats['avg_cpu'] = round(sum(cpus) / len(cpus), 2)
                
                stats['total_records'] = records_today # Mostrar registros de hoy en el dashboard
                stats['uptime_percent'] = round((online_count / len(latency_data) * 100), 1) if latency_data else 0
            
            if self.last_sync_time:
                stats['last_sync'] = self.last_sync_time.isoformat()
                
            return stats
            
        except Exception as e:
            logger.error(f"Error stats: {e}")
            return self._get_default_stats()

    def _get_default_stats(self) -> Dict[str, Any]:
        return {
            'avg_latency': 0, 'avg_cpu': 0, 'total_records': 0, 'total_devices': 0,
            'uptime_percent': 0, 'last_sync': None
        }
