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
    """Servicio para interactuar con AppSheet Database - CORREGIDO ARGOS"""
    
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY', '')
        self.app_id = os.getenv('APPSHEET_APP_ID', '')
        self.base_url = os.getenv('APPSHEET_BASE_URL', 'https://api.appsheet.com/api/v2')
        
        env_enabled = os.getenv('APPSHEET_ENABLED', 'false').lower()
        is_config_enabled = env_enabled in ['true', '1', 'yes', 'on']
        # Validación básica de credenciales
        has_creds = self.api_key and self.app_id and 'tu_api_key' not in self.api_key

        if not is_config_enabled or not has_creds:
            self.enabled = False
            logger.warning("AppSheetService deshabilitado - Configuración incompleta")
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService Conectado - App ID: {self.app_id[:10]}...")

    def _make_appsheet_request(self, table: str, action: str, rows: List[Dict] = None, properties: Dict = None) -> Optional[Any]:
        """Método genérico para hacer peticiones a AppSheet"""
        try:
            if not self.enabled: 
                return None
            
            payload = {
                "Action": action, 
                "Properties": {
                    "Locale": "es-MX",
                    "Timezone": "Central Standard Time"
                }
            }
            
            if properties:
                payload["Properties"].update(properties)
            
            if rows: 
                payload["Rows"] = rows
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            # logger.debug(f"📤 AppSheet Payload ({table}): {json.dumps(payload, indent=2)[:500]}")
            
            response = requests.post(
                url,
                headers=self.headers, 
                json=payload, 
                timeout=30
            )
            
            if response.status_code == 200:
                try: 
                    result = response.json()
                    return result
                except Exception:
                    return {"success": True, "raw_text": response.text}
            
            # ERROR 400 - DIAGNÓSTICO
            logger.error(f"❌ AppSheet Error {response.status_code} en tabla '{table}':")
            logger.error(f"   URL: {url}")
            logger.error(f"   Response: {response.text}") # IMPORTANTE: Ver qué columna falla
            
            return None
            
        except Exception as e:
            logger.error(f"Error crítico en petición AppSheet: {e}")
            return None

    def generate_device_id(self, pc_name: str) -> str:
        """Genera un ID único y consistente (HASH)"""
        try:
            if not pc_name or not pc_name.strip():
                return "UNKNOWN_ID"
                
            pc_name = pc_name.strip().upper()
            
            # Lógica para preservar IDs tipo MX_
            if pc_name.startswith("MX_"):
                parts = pc_name.split(' ')
                if len(parts) > 0:
                    mx_part = parts[0].strip()
                    if len(mx_part) > 3:
                        return mx_part
            
            hash_result = hashlib.md5(pc_name.encode()).hexdigest()[:12].upper()
            return f"HASH_{hash_result}"
            
        except Exception:
            return "ERROR_ID"

    def get_or_create_device(self, device_data: Dict) -> tuple:
        """
        Maneja la tabla 'devices'.
        Schema esperado: device_id, pc_name, unit, public_ip, last_known_location, is_active, updated_at
        """
        try:
            if not self.enabled: return False, None, False
            
            pc_name = device_data.get('pc_name', '').strip()
            if not pc_name: return False, None, False
            
            device_id = self.generate_device_id(pc_name)
            
            # Preparar fila EXACTAMENTE como la pide la base de datos
            status_str = device_data.get('status', 'online')
            is_active = "TRUE" if status_str == 'online' else "FALSE"
            
            device_row = {
                "device_id": device_id,
                "pc_name": pc_name,
                "unit": device_data.get('unit', 'General'),
                "public_ip": device_data.get('public_ip', device_data.get('ip', '')),
                "is_active": is_active, # CORREGIDO: status -> is_active
                "updated_at": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S') # Formato String limpio
            }
            
            # Opcional: Agregar last_known_location si tienes coordenadas
            # device_row["last_known_location"] = "0,0" 

            logger.info(f"🔄 Sincronizando dispositivo: {pc_name} (ID: {device_id})")
            
            # Usamos "Add" que en AppSheet actúa como "Upsert" (Actualizar si existe, Crear si no)
            # siempre y cuando la llave primaria (device_id) coincida.
            result = self._make_appsheet_request("devices", "Add", [device_row])
            
            if result is not None:
                self.last_sync_time = datetime.now(TZ_MX)
                return True, device_id, True
            else:
                return False, device_id, False
                
        except Exception as e:
            logger.error(f"Error en get_or_create_device: {e}")
            return False, None, False

    def add_latency_to_history(self, device_data: Dict) -> bool:
        """
        Maneja la tabla 'Latency_history'.
        Schema esperado: record_id, device_id, timestamp, latency_ms, cpu_percent, ram_percent, temperature_c, disk_percent, status, extended_sensors
        """
        try:
            if not self.enabled: return False
            
            pc_name = device_data.get('pc_name', '')
            if not pc_name: return False
            
            device_id = self.generate_device_id(pc_name)
            
            # Generar UUID para el registro histórico
            record_id = str(uuid.uuid4())
            
            # Mapeo estricto de columnas
            latency_record = {
                "record_id": record_id, # IMPORTANTE: Llave única
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "latency_ms": str(device_data.get('latency', 0)), # CORREGIDO: latency -> latency_ms
                "cpu_percent": str(device_data.get('cpu_load_percent', 0)), # CORREGIDO: cpu_load -> cpu_percent
                "ram_percent": str(device_data.get('ram_percent', 0)),
                "temperature_c": str(device_data.get('temperature', 0)), # CORREGIDO: temperature -> temperature_c
                "disk_percent": str(device_data.get('disk_percent', 0)),
                "status": device_data.get('status', 'online'),
                "extended_sensors": str(device_data.get('extended_sensors', ''))[:1000] # Truncar por seguridad
            }
            
            logger.info(f"📊 Enviando latencia para {pc_name}")
            result = self._make_appsheet_request("Latency_history", "Add", [latency_record])
            
            return result is not None
                
        except Exception as e:
            logger.error(f"Error en add_latency_to_history: {e}")
            return False

    def add_history_entry(self, log_data: Dict) -> bool:
        """
        Maneja la tabla 'device_history'.
        Schema esperado: history_id, device_id, timestamp, requester, executor, action_type, component, description, is_resolved, location_snapshot, unit_snapshot
        """
        try:
            if not self.enabled: return False

            device_name = log_data.get('device_name') or log_data.get('pc_name')
            if not device_name: return False

            # 1. Asegurar dispositivo en tabla padre
            success, device_id, _ = self.get_or_create_device({
                "pc_name": device_name,
                "unit": log_data.get('unit', 'General'),
                "status": 'online'
            })
            
            if not success:
                logger.warning("No se pudo verificar dispositivo padre, intentando guardar historial de todos modos...")
                device_id = self.generate_device_id(device_name)

            # 2. Mapeo estricto para device_history
            history_id = str(uuid.uuid4())
            is_resolved = "TRUE" if log_data.get('solved') or log_data.get('is_resolved') else "FALSE"
            
            history_row = {
                "history_id": history_id, # Nueva llave única
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "requester": str(log_data.get('req', log_data.get('requester', 'Sistema'))),
                "executor": str(log_data.get('exec', log_data.get('executor', 'Sistema'))),
                "action_type": str(log_data.get('action', log_data.get('action_type', 'Mantenimiento'))),
                "component": str(log_data.get('what', log_data.get('component', 'General'))),
                "description": str(log_data.get('desc', log_data.get('description', ''))),
                "is_resolved": is_resolved,
                "unit_snapshot": str(log_data.get('unit', 'General')),
                "location_snapshot": str(device_name) # Faltaba este campo requerido
            }
            
            logger.info(f"📝 Guardando bitácora para {device_name}")
            result = self._make_appsheet_request("device_history", "Add", [history_row])
            
            return result is not None

        except Exception as e:
            logger.error(f"Error en add_history_entry: {e}")
            return False

    # --- Métodos de Ayuda / Compatibilidad ---

    def list_available_tables(self) -> List[str]:
        return ["devices", "device_history", "Latency_history", "alerts"]

    def get_status_info(self) -> Dict:
        return {
            "status": "enabled" if self.enabled else "disabled", 
            "last_sync": str(self.last_sync_time)
        }
        
    def get_system_stats(self) -> Dict:
        return {"status": "ok"} # Simplificado para evitar errores 400 en lecturas complejas

    def sync_device_complete(self, device_data: Dict) -> bool:
        """Compatibilidad con monitor_service"""
        success, _, _ = self.get_or_create_device(device_data)
        return success
    
    def upsert_device(self, device_data: Dict) -> bool:
        """Compatibilidad con monitor_service"""
        return self.sync_device_complete(device_data)
    
    def add_latency_record(self, device_data: Dict) -> bool:
        """Compatibilidad con monitor_service"""
        return self.add_latency_to_history(device_data)

    def add_alert(self, device_data: Dict, alert_type: str, message: str, severity: str) -> bool:
        """Compatibilidad con monitor_service"""
        # Redirige a history ya que alerts tiene un esquema distinto que no hemos mapeado
        return self.add_history_entry({
            "device_name": device_data.get('pc_name'),
            "action": "ALERTA",
            "what": alert_type,
            "desc": f"[{severity}] {message}",
            "req": "Watchdog",
            "solved": False
        })
    
    # --- Métodos de Lectura (Read) ---
    # Nota: AppSheet FilterQuery es delicado. Si falla, devolver lista vacía para no romper el front.
    
    def get_full_history(self, limit: int = 200) -> List[Dict]:
        res = self._make_appsheet_request("device_history", "Find", properties={"Top": limit})
        return res if isinstance(res, list) else []

    def get_history_for_device(self, pc_name: str) -> List[Dict]:
        # Para evitar complejidad de filtros, traemos los últimos y filtramos en memoria
        # AppSheet Database a veces falla con selectores complejos vía API REST
        all_rows = self.get_full_history(300)
        device_id = self.generate_device_id(pc_name)
        return [r for r in all_rows if r.get('device_id') == device_id]
