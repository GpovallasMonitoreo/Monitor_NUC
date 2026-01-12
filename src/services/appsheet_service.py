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
        # Lectura segura de Variables de Entorno
        self.api_key = os.getenv('APPSHEET_API_KEY', '')
        self.app_id = os.getenv('APPSHEET_APP_ID', '')
        self.base_url = os.getenv('APPSHEET_BASE_URL', 'https://api.appsheet.com/api/v2')
        
        # Verificar flag de habilitado (maneja strings 'true', 'True', '1')
        env_enabled = os.getenv('APPSHEET_ENABLED', 'false').lower()
        is_config_enabled = env_enabled in ['true', '1', 'yes', 'on']

        # Verificar credenciales
        has_creds = self.api_key and self.app_id and 'tu_api_key' not in self.api_key

        if not is_config_enabled:
            logger.info("ℹ️ AppSheet deshabilitado por variable de entorno (APPSHEET_ENABLED)")
            self.enabled = False
            return

        if not has_creds:
            logger.warning("⚠️ AppSheet habilitado pero faltan credenciales válidas")
            self.enabled = False
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService inicializado correctamente (AppID: {self.app_id[:5]}...)")
        
        # Test rápido silencioso
        try:
            self._test_table_connection('devices')
        except:
            pass
    
    def _test_table_connection(self, table_name: str) -> bool:
        try:
            if not self.enabled: return False
            payload = {
                "Action": "Find",
                "Properties": {"Locale": "en-US", "Top": 1}
            }
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/{table_name}/Action",
                headers=self.headers,
                json=payload,
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def generate_device_id(self, pc_name: str) -> str:
        return hashlib.md5(pc_name.encode()).hexdigest()[:16].upper()
    
    def is_available(self) -> bool:
        return self.enabled
    
    def _make_safe_request(self, table: str, action: str, rows: List[Dict] = None) -> Optional[Any]:
        try:
            if not self.enabled: return None
            
            payload = {
                "Action": action,
                "Properties": {"Locale": "en-US"}
            }
            if rows: payload["Rows"] = rows
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                try:
                    return response.json()
                except:
                    return {"success": True}
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
            
            # Estrategia: Intentar Add, si falla no importa (ya existe), luego Edit si es necesario
            # Simplificado: Usamos Add, AppSheet suele manejarlo bien si la Key coincide
            self._make_safe_request("devices", "Add", [device_row])
            
            # Actualizamos también con Edit por si acaso ya existía y Add falló silenciosamente
            self._make_safe_request("devices", "Edit", [device_row])
            
            self.last_sync_time = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Error upsert_device: {e}")
            return False

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
        except Exception:
            return False

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
        except Exception:
            return False
            
    def sync_device_complete(self, device_data: Dict):
        """Sincronización completa forzada"""
        self.upsert_device(device_data)
        self.add_latency_record(device_data)

    def get_status_info(self) -> Dict[str, Any]:
        """Información de estado para el Dashboard"""
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "AppSheet deshabilitado o credenciales inválidas",
                "available": False,
                "last_sync": None
            }
        
        # Test real al momento de pedir status
        connection_ok = self._test_table_connection('devices')
        
        return {
            "status": "enabled",
            "available": connection_ok,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "message": "Conectado a AppSheet" if connection_ok else "Error de conexión con AppSheet",
            "has_api_key": bool(self.api_key),
            "app_id_preview": f"...{self.app_id[-4:]}" if self.app_id else "N/A"
        }
