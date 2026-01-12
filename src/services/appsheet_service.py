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
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY', '')
        self.app_id = os.getenv('APPSHEET_APP_ID', '')
        self.base_url = os.getenv('APPSHEET_BASE_URL', 'https://api.appsheet.com/api/v2')
        
        env_enabled = os.getenv('APPSHEET_ENABLED', 'false').lower()
        self.enabled = env_enabled in ['true', '1', 'yes', 'on'] and self.api_key and self.app_id

        if self.enabled:
            self.headers = {'Content-Type': 'application/json', 'ApplicationAccessKey': self.api_key}
            logger.info(f"✅ AppSheetService Conectado")
        else:
            logger.warning("⚠️ AppSheet Deshabilitado")

    # --- MÉTODOS AUXILIARES ---
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

    # --- MÉTODOS DE LECTURA Y ESCRITURA ---

    def get_status_info(self) -> Dict[str, Any]:
        return {"status": "enabled" if self.enabled else "disabled", "available": self.enabled}

    def upsert_device(self, device_data: Dict) -> bool:
        """Actualiza inventario de dispositivos"""
        try:
            device_id = self.generate_device_id(device_data['pc_name'])
            row = {
                "device_id": device_id,
                "pc_name": device_data['pc_name'],
                "unit": device_data.get('unit', 'General'),
                "public_ip": device_data.get('public_ip', device_data.get('ip', '')),
                "status": device_data.get('status', 'online'),
                "updated_at": datetime.now(TZ_MX).isoformat()
            }
            self._make_safe_request("devices", "Add", [row]) # Add suele funcionar como Upsert
            return True
        except: return False

    def add_latency_record(self, device_data: Dict) -> bool:
        """Agrega historial de métricas"""
        # (Código igual al anterior, omitido por brevedad pero necesario en el archivo final)
        try:
            device_id = self.generate_device_id(device_data['pc_name'])
            row = {
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).isoformat(),
                "latency_ms": float(device_data.get('latency', 0)),
                "cpu_percent": float(device_data.get('cpu_load_percent', 0)),
                "status": str(device_data.get('status', 'online'))
            }
            self._make_safe_request("latency_history", "Add", [row])
            return True
        except: return False

    def get_system_stats(self) -> Dict[str, Any]:
        # (Tu lógica de estadísticas anterior va aquí)
        return {'avg_latency': 0, 'total_devices': 0}

    # --- NUEVOS MÉTODOS PARA BITÁCORA ---

    def add_history_entry(self, log_data: Dict) -> bool:
        """Guarda un registro en la bitácora 'device_history'"""
        try:
            if not self.enabled: return False
            
            device_id = self.generate_device_id(log_data.get('device_name', ''))
            
            history_row = {
                # AppSheet genera ID automáticamente si es Key
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).isoformat(),
                "requester": log_data.get('req', ''),
                "executor": log_data.get('exec', ''),
                "action_type": log_data.get('action', ''),
                "component": log_data.get('what', ''),
                "description": log_data.get('desc', ''),
                "is_resolved": str(log_data.get('solved', False)).lower(),
                "location_snapshot": log_data.get('locName', ''),
                "unit_snapshot": log_data.get('unit', 'General'),
                "status_snapshot": log_data.get('status_snapshot', 'active') # Para el filtro activo/inactivo
            }
            
            logger.info(f"Enviando a Bitácora: {history_row}")
            return self._make_safe_request("device_history", "Add", [history_row]) is not None
        except Exception as e:
            logger.error(f"Error add_history_entry: {e}")
            return False

    def get_full_history(self) -> List[Dict]:
        """Obtiene TODOS los registros de la bitácora para la tabla"""
        try:
            if not self.enabled: return []
            # Trae todo el historial
            data = self._make_safe_request("device_history", "Find", [])
            if isinstance(data, list):
                # Ordenar por fecha descendente
                return sorted(data, key=lambda x: x.get('timestamp', ''), reverse=True)
            return []
        except Exception as e:
            logger.error(f"Error get_full_history: {e}")
            return []
