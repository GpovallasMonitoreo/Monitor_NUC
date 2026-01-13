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
    Servicio para interactuar con AppSheet API v2.
    CORREGIDO POR ARGOS:
    - URL base forzada a endpoint API REST.
    - Mapeo estricto de columnas (latency_ms, cpu_percent, is_active).
    - Generación de UUIDs para tablas de historial.
    """
    
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY', '')
        self.app_id = os.getenv('APPSHEET_APP_ID', '')
        
        # --- FIX ARGOS: URL ESTÁNDAR ---
        # Ignoramos cualquier configuración externa incorrecta.
        # La API de AppSheet SIEMPRE vive aquí:
        self.base_url = "https://api.appsheet.com/api/v2"
        
        env_enabled = os.getenv('APPSHEET_ENABLED', 'false').lower()
        is_config_enabled = env_enabled in ['true', '1', 'yes', 'on']
        has_creds = self.api_key and self.app_id and 'tu_api_key' not in self.api_key

        if not is_config_enabled or not has_creds:
            self.enabled = False
            logger.warning("AppSheetService deshabilitado - Configuración incompleta o credenciales default")
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService Iniciado - Target: {self.app_id[:8]}...")

    def _make_appsheet_request(self, table: str, action: str, rows: List[Dict] = None, properties: Dict = None) -> Optional[Any]:
        """Envía petición HTTP a la API de AppSheet con manejo de errores robusto"""
        try:
            if not self.enabled: return None
            
            # Construcción del Wrapper API
            payload = {
                "Action": action, 
                "Properties": {
                    "Locale": "es-MX",
                    "Timezone": "Central Standard Time"
                }
            }
            
            if properties: payload["Properties"].update(properties)
            if rows: payload["Rows"] = rows
            
            # URL Definitiva
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            # logger.debug(f"📤 Payload a {table}: {json.dumps(payload, indent=2)[:200]}...")
            
            response = requests.post(
                url,
                headers=self.headers, 
                json=payload, 
                timeout=30
            )
            
            if response.status_code == 200:
                self.last_sync_time = datetime.now(TZ_MX)
                try: 
                    return response.json()
                except:
                    return {"success": True}
            
            # MANEJO DE ERROR 400 DETALLADO
            logger.error(f"❌ AppSheet Error {response.status_code} en tabla '{table}':")
            logger.error(f"   URL Objetivo: {url}")
            try:
                # AppSheet suele devolver un JSON explicando qué columna falló
                error_json = response.json()
                logger.error(f"   Detalle API: {json.dumps(error_json, indent=2)}")
            except:
                # Si no es JSON, mostrar texto crudo (HTML o String)
                logger.error(f"   Respuesta Raw: {response.text}")
            
            return None
            
        except Exception as e:
            logger.error(f"🔥 Excepción crítica en AppSheet Service: {e}")
            return None

    def generate_device_id(self, pc_name: str) -> str:
        """Genera un ID determinista basado en el nombre del PC"""
        try:
            if not pc_name or not pc_name.strip():
                return "UNKNOWN_ID"
                
            clean_name = pc_name.strip().upper()
            
            # Si ya tiene formato MX_, intentamos preservarlo
            if clean_name.startswith("MX_"):
                parts = clean_name.split(' ')
                if len(parts) > 0 and len(parts[0]) > 3:
                    return parts[0].strip()
            
            # Fallback a Hash MD5
            hash_result = hashlib.md5(clean_name.encode()).hexdigest()[:12].upper()
            return f"HASH_{hash_result}"
            
        except Exception:
            return "ERROR_ID"

    # ==========================================================
    # MÉTODOS DE NEGOCIO (Con Mapeo de Columnas Corregido)
    # ==========================================================

    def get_or_create_device(self, device_data: Dict) -> tuple:
        """
        Sincroniza tabla 'devices'.
        Columns: device_id, pc_name, unit, public_ip, is_active, updated_at
        """
        try:
            if not self.enabled: return False, None, False
            
            pc_name = device_data.get('pc_name', '').strip()
            if not pc_name: return False, None, False
            
            device_id = self.generate_device_id(pc_name)
            
            # MAPEO STATUS -> IS_ACTIVE
            status_val = device_data.get('status', 'online')
            is_active = "TRUE" if status_val == 'online' else "FALSE"
            
            device_row = {
                "device_id": device_id,
                "pc_name": pc_name,
                "unit": device_data.get('unit', 'General'),
                "public_ip": device_data.get('public_ip', device_data.get('ip', '')),
                "is_active": is_active,
                "updated_at": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # logger.info(f"🔄 Sync Device: {pc_name} -> {device_id}")
            result = self._make_appsheet_request("devices", "Add", [device_row])
            
            if result is not None:
                return True, device_id, True
            return False, device_id, False
                
        except Exception as e:
            logger.error(f"Error en get_or_create_device: {e}")
            return False, None, False

    def add_latency_to_history(self, device_data: Dict) -> bool:
        """
        Sincroniza tabla 'Latency_history'.
        Columns: record_id, device_id, latency_ms, cpu_percent, temperature_c, etc.
        """
        try:
            if not self.enabled: return False
            
            pc_name = device_data.get('pc_name', '')
            if not pc_name: return False
            
            device_id = self.generate_device_id(pc_name)
            
            # Generar Primary Key única para el historial
            record_id = str(uuid.uuid4())
            
            # MAPEO DE SENSORES
            row = {
                "record_id": record_id,
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "latency_ms": str(device_data.get('latency', 0)),
                "cpu_percent": str(device_data.get('cpu_load_percent', 0)),
                "ram_percent": str(device_data.get('ram_percent', 0)),
                "temperature_c": str(device_data.get('temperature', 0)),
                "disk_percent": str(device_data.get('disk_percent', 0)),
                "status": device_data.get('status', 'online'),
                # Truncamos extended_sensors para no romper límites de celda
                "extended_sensors": str(device_data.get('extended_sensors', ''))[:2000]
            }
            
            # logger.info(f"📊 Sending Latency History for {pc_name}")
            result = self._make_appsheet_request("Latency_history", "Add", [row])
            return result is not None
                
        except Exception as e:
            logger.error(f"Error en add_latency_to_history: {e}")
            return False

    def add_history_entry(self, log_data: Dict) -> bool:
        """
        Sincroniza tabla 'device_history' (Bitácora).
        """
        try:
            if not self.enabled: return False

            dev_name = log_data.get('device_name') or log_data.get('pc_name')
            if not dev_name: return False

            # 1. Asegurar que el padre existe
            success, device_id, _ = self.get_or_create_device({
                "pc_name": dev_name,
                "unit": log_data.get('unit', 'General')
            })
            
            if not success:
                device_id = self.generate_device_id(dev_name) # Fallback

            # 2. Preparar Ficha
            history_id = str(uuid.uuid4())
            is_resolved = "TRUE" if log_data.get('solved') or log_data.get('is_resolved') else "FALSE"
            
            row = {
                "history_id": history_id,
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "requester": str(log_data.get('req', log_data.get('requester', 'Sistema'))),
                "executor": str(log_data.get('exec', log_data.get('executor', 'Sistema'))),
                "action_type": str(log_data.get('action', log_data.get('action_type', 'Mantenimiento'))),
                "component": str(log_data.get('what', log_data.get('component', 'General'))),
                "description": str(log_data.get('desc', log_data.get('description', ''))),
                "is_resolved": is_resolved,
                "unit_snapshot": str(log_data.get('unit', 'General')),
                "location_snapshot": str(dev_name)
            }
            
            logger.info(f"📝 Guardando Bitácora: {dev_name} - {row['action_type']}")
            result = self._make_appsheet_request("device_history", "Add", [row])
            return result is not None

        except Exception as e:
            logger.error(f"Error en add_history_entry: {e}")
            return False

    # ==========================================================
    # MÉTODOS DE COMPATIBILIDAD (Interfaces para MonitorService)
    # ==========================================================
    
    def sync_device_complete(self, data: Dict) -> bool:
        success, _, _ = self.get_or_create_device(data)
        return success
    
    def upsert_device(self, data: Dict) -> bool:
        return self.sync_device_complete(data)
    
    def add_latency_record(self, data: Dict) -> bool:
        return self.add_latency_to_history(data)

    def add_alert(self, data: Dict, type: str, msg: str, sev: str) -> bool:
        # Redirige alertas a la bitácora general
        return self.add_history_entry({
            "device_name": data.get('pc_name'),
            "action": "ALERTA",
            "what": type,
            "desc": f"[{sev.upper()}] {msg}",
            "req": "Watchdog",
            "solved": False,
            "unit": data.get('unit', 'General')
        })

    # ==========================================================
    # MÉTODOS DE LECTURA / UTILS
    # ==========================================================

    def list_available_tables(self) -> List[str]:
        return ["devices", "device_history", "Latency_history", "alerts"]

    def get_status_info(self) -> Dict:
        return {"status": "enabled" if self.enabled else "disabled", "last_sync": str(self.last_sync_time)}
        
    def get_system_stats(self) -> Dict:
        # Dummy stats para no saturar la API en el dashboard
        return {"status": "ok", "message": "Estadísticas en vivo deshabilitadas por optimización"}

    def get_full_history(self, limit: int = 200) -> List[Dict]:
        res = self._make_appsheet_request("device_history", "Find", properties={"Top": limit})
        return res if isinstance(res, list) else []

    def get_history_for_device(self, pc_name: str) -> List[Dict]:
        # Traer reciente y filtrar en memoria es más robusto en AppSheet que filtrar por API complicada
        all_rows = self.get_full_history(300)
        target_id = self.generate_device_id(pc_name)
        return [r for r in all_rows if r.get('device_id') == target_id]
