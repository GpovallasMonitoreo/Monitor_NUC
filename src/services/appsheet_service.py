import os
import requests
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

# Configuración de Zona Horaria (CDMX)
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
            logger.info("ℹ️ AppSheet deshabilitado o sin credenciales")
            self.enabled = False
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService Conectado (AppID: {self.app_id[:5]}...)")

        # Test silencioso de conexión
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
                # Validación básica: que tenga longitud razonable para ser un ID
                if len(parts) > 0 and len(parts[0]) > 5:
                    return parts[0].strip()
            
            # Fallback: Hash MD5
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
                headers=self.headers, json=payload, timeout=20
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

            now_mx = datetime.now(TZ_MX).isoformat()

            device_row = {
                "device_id": device_id,
                "pc_name": device_data['pc_name'],
                "unit": device_data.get('unit', 'General'),
                "public_ip": device_data.get('public_ip', device_data.get('ip', '')),
                "last_known_location": location,
                "is_active": device_data.get('status', 'online') != 'offline',
                "status": device_data.get('status', 'online'),
                "updated_at": now_mx
            }
            # Intentar Add y luego Edit para asegurar
            self._make_safe_request("devices", "Add", [device_row])
            self._make_safe_request("devices", "Edit", [device_row])
            self.last_sync_time = datetime.now(TZ_MX)
            return True
        except Exception: return False

    def add_latency_record(self, device_data: Dict) -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Helper para obtener temperatura
            def get_temp_safe(data):
                try:
                    t = data.get('temperature')
                    if t is not None: return float(t)
                    if data.get('extended_sensors') and 'Intel CPU' in data['extended_sensors']:
                        sensors = data['extended_sensors']['Intel CPU']
                        for s in sensors:
                            if s.get('tipo') == 'Temperature': return float(s.get('valor', 0))
                except: pass
                return 40.0

            now_mx = datetime.now(TZ_MX).isoformat()

            latency_row = {
                "device_id": device_id,
                "timestamp": now_mx,
                "latency_ms": float(device_data.get('latency', 0)),
                "cpu_percent": float(device_data.get('cpu_load_percent', 0)),
                "ram_percent": float(device_data.get('ram_percent', 0)),
                "temperature_c": get_temp_safe(device_data),
                "status": str(device_data.get('status', 'online'))
            }
            self._make_safe_request("latency_history", "Add", [latency_row])
            return True
        except Exception: return False

    def add_alert(self, device_data: Dict, alert_type: str, message: str, severity: str = "medium") -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(device_data['pc_name'])
            now_mx = datetime.now(TZ_MX).isoformat()

            alert_row = {
                "device_id": device_id,
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "timestamp": now_mx,
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
        """Calcula estadísticas con fechas corregidas a CDMX"""
        try:
            if not self.enabled: return self._get_default_stats()
            
            stats = self._get_default_stats()

            # 1. Total dispositivos
            devices_response = self._make_safe_request("devices", "Find", [])
            if isinstance(devices_response, list):
                stats['total_devices'] = len(devices_response)
            
            # 2. Historial
            latency_data = self._make_safe_request("latency_history", "Get") or []
            if not isinstance(latency_data, list): latency_data = []
            
            if latency_data:
                latencies = []
                cpus = []
                online_count = 0
                
                # Registros de hoy
                today_mx = datetime.now(TZ_MX).date()
                records_today = 0

                for row in latency_data:
                    try:
                        ts_str = str(row.get('timestamp', ''))
                        row_date = None
                        
                        if 'T' in ts_str:
                            row_date = datetime.fromisoformat(ts_str.replace('Z', '')).date()
                        elif ' ' in ts_str:
                            row_date = datetime.strptime(ts_str.split('.')[0], '%Y-%m-%d %H:%M:%S').date()
                        elif '/' in ts_str:
                            row_date = datetime.strptime(ts_str.split(' ')[0], '%m/%d/%Y').date()

                        if row_date and row_date == today_mx:
                            records_today += 1

                        if row.get('latency_ms'): latencies.append(float(row['latency_ms']))
                        if row.get('cpu_percent'): cpus.append(float(row['cpu_percent']))
                        if row.get('status') == 'online': online_count += 1
                    except Exception: 
                        continue
                
                if latencies: stats['avg_latency'] = round(sum(latencies) / len(latencies), 2)
                if cpus: stats['avg_cpu'] = round(sum(cpus) / len(cpus), 2)
                
                stats['total_records'] = records_today
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

    # ==========================================
    # MÉTODOS DE BITÁCORA (DEVICE HISTORY)
    # ==========================================

    def add_history_entry(self, log_data: Dict) -> bool:
        """
        Registra un evento en la bitácora detallada.
        Se vincula automáticamente con el device_id.
        """
        try:
            if not self.enabled: return False
            
            # Generamos el ID del dispositivo para vincular
            device_id = self.generate_device_id(log_data.get('device_name', ''))
            
            history_row = {
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).isoformat(),
                
                # Campos del Formulario
                "requester": log_data.get('req', 'Sistema'),
                "executor": log_data.get('exec', 'Pendiente'),
                "action_type": log_data.get('action', 'Mantenimiento'),
                "component": log_data.get('what', '-'),
                "description": log_data.get('desc', ''),
                "is_resolved": str(log_data.get('solved', False)).lower(), # AppSheet prefiere strings o booleanos directos
                
                # Snapshots del momento
                "location_snapshot": log_data.get('locName', ''),
                "unit_snapshot": log_data.get('unit', 'General'),
                "status_snapshot": log_data.get('status_snapshot', 'active')
            }
            
            # Enviamos a la tabla 'device_history'
            result = self._make_safe_request("device_history", "Add", [history_row])
            
            if result is not None:
                logger.info(f"✅ Bitácora actualizada para {log_data.get('device_name')}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error agregando historial: {e}")
            return False

    def get_full_history(self) -> List[Dict]:
        """
        Obtiene TODOS los registros de la bitácora para mostrarlos en la tabla global.
        """
        try:
            if not self.enabled: return []
            
            # Trae todo el historial
            data = self._make_safe_request("device_history", "Get", [])
            
            if isinstance(data, list):
                # Ordenar por fecha descendente (más reciente primero)
                return sorted(data, key=lambda x: x.get('timestamp', ''), reverse=True)
            return []
            
        except Exception as e:
            logger.error(f"Error get_full_history: {e}")
            return []
