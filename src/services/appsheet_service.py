# src/services/appsheet_service.py - VERSIÓN DE EMERGENCIA CORREGIDA
import os
import requests
import json
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class AppSheetService:
    """Servicio AppSheet - VERSIÓN CORREGIDA DEFINITIVA"""
    
    def __init__(self):
        # Obtener credenciales
        self.api_key = os.getenv('APPSHEET_API_KEY', '').strip()
        self.app_id = os.getenv('APPSHEET_APP_ID', '').strip()
        enabled_env = os.getenv('APPSHEET_ENABLED', 'true').strip().lower()
        
        # ¡IMPORTANTE! enabled debe ser BOOLEANO
        self.enabled = enabled_env in ['true', '1', 'yes', 'on'] and bool(self.api_key and self.app_id)
        self.base_url = "https://api.appsheet.com/api/v2"
        self.headers = {
            'Content-Type': 'application/json', 
            'ApplicationAccessKey': self.api_key
        }
        
        # Estado de conexión por tabla
        self.table_status = {}
        self.last_sync_time = None
        
        logger.info(f"AppSheet Service: {'ENABLED' if self.enabled else 'DISABLED'}")
        logger.info(f"App ID: {self.app_id[:15]}..." if self.app_id else "No App ID")
        logger.info(f"Enabled (boolean): {self.enabled}")
        
        if self.enabled:
            self._test_all_tables()
    
    def _test_all_tables(self):
        """Prueba conexión con todas las tablas"""
        tables_to_test = ["devices", "device_history", "latency_history", "alerts"]
        
        logger.info("🔍 Probando conexión con tablas...")
        for table_name in tables_to_test:
            try:
                result = self._make_safe_request(
                    table_name, 
                    "Find",
                    properties={"Locale": "es-MX", "Top": 1}
                )
                
                self.table_status[table_name] = result is not None
                status = "✅" if result else "❌"
                logger.info(f"  {status} Tabla '{table_name}': {'Conectada' if result else 'No encontrada'}")
                
            except Exception as e:
                self.table_status[table_name] = False
                logger.info(f"  ❌ Tabla '{table_name}': Error - {str(e)[:50]}")
    
    def _make_safe_request(self, table: str, action: str, rows: List[Dict] = None, 
                          properties: Dict = None) -> Optional[Any]:
        """Envía petición HTTP"""
        if not self.enabled:
            return None
        
        try:
            final_props = {"Locale": "es-MX", "Timezone": "Central Standard Time"}
            if properties:
                final_props.update(properties)
            
            payload = {"Action": action, "Properties": final_props}
            
            if rows:
                payload["Rows"] = rows
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                if not response.text or response.text.strip() == "":
                    return {"status": "success", "message": "empty_response"}
                
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"status": "success", "raw": response.text}
            
            return None
                
        except Exception as e:
            logger.error(f"Error en {table}.{action}: {str(e)}")
            return None
    
    def get_or_create_device(self, device_data: Dict) -> tuple:
        """Crea o actualiza un dispositivo"""
        try:
            if not self.enabled:
                return False, None, False
            
            pc_name = str(device_data.get('pc_name', '')).strip()
            if not pc_name:
                return False, None, False
            
            device_id = self._generate_device_id(pc_name)
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            row = {
                "device_id": device_id,
                "pc_name": pc_name,
                "unit": str(device_data.get('unit', 'General')),
                "public_ip": str(device_data.get('public_ip', device_data.get('ip', ''))),
                "last_known_location": str(device_data.get('locName', pc_name)),
                "is_active": "true",
                "created_at": ts,
                "updated_at": ts
            }
            
            result = self._make_safe_request("devices", "Add", [row])
            
            if result:
                self.last_sync_time = datetime.now()
                return True, device_id, True
            else:
                return False, device_id, False
                
        except Exception as e:
            logger.error(f"Error en get_or_create_device: {e}")
            return False, None, False
    
    def add_history_entry(self, log_data: Dict) -> bool:
        """Añade una entrada al historial"""
        try:
            if not self.enabled:
                return False
            
            pc_name = log_data.get('pc_name') or log_data.get('device_name', '')
            if not pc_name:
                return False
            
            device_id = self._generate_device_id(pc_name)
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            row = {
                "device_id": device_id,
                "pc_name": pc_name,
                "exec": str(log_data.get('exec', 'Sistema')),
                "action": str(log_data.get('action', 'Info')),
                "what": str(log_data.get('what', 'General')),
                "desc": str(log_data.get('desc', 'NA')),
                "solved": str(log_data.get('solved', 'true')).lower(),
                "locName": str(log_data.get('locName', pc_name)),
                "unit": str(log_data.get('unit', 'General')),
                "status_snapshot": str(log_data.get('status_snapshot', 'active')),
                "timestamp": ts
            }
            
            result = self._make_safe_request("device_history", "Add", [row])
            
            if result:
                self.last_sync_time = datetime.now()
                
            return result is not None
            
        except Exception as e:
            logger.error(f"Error en add_history_entry: {e}")
            return False
    
    def _generate_device_id(self, pc_name: str) -> str:
        """Genera ID consistente"""
        try:
            if not pc_name:
                return "UNKNOWN_" + str(uuid.uuid4())[:8]
            
            clean = pc_name.strip().upper()
            
            if clean.startswith("MX_") and len(clean) > 4:
                parts = clean.split(' ')
                if len(parts) > 0:
                    return parts[0].strip()
            
            hash_obj = hashlib.md5(clean.encode())
            return f"HASH_{hash_obj.hexdigest()[:10].upper()}"
            
        except Exception:
            return "ERROR_" + str(uuid.uuid4())[:8]
    
    def get_full_history(self, limit: int = 50) -> List[Dict]:
        """Obtiene todo el historial"""
        try:
            if not self.enabled:
                return []
            
            result = self._make_safe_request(
                "device_history", 
                "Find", 
                properties={"Top": limit, "OrderBy": "[timestamp] DESC"}
            )
            
            if result and isinstance(result, list):
                return result[:limit]
            elif result and isinstance(result, dict) and 'Rows' in result:
                return result['Rows'][:limit]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error en get_full_history: {e}")
            return []
    
    def get_status_info(self) -> Dict:
        """Obtiene información de estado - VERSIÓN FINAL CORREGIDA"""
        is_connected = any(self.table_status.values()) if self.table_status else False
        
        # ¡CRÍTICO! enabled debe ser BOOLEANO, no string
        return {
            "enabled": self.enabled,  # ← Booleano
            "connection_status": "connected" if is_connected else "disconnected",
            "tables": self.table_status,
            "has_credentials": bool(self.api_key and self.app_id),
            "app_id": self.app_id,  # ← String separado
            "app_id_preview": self.app_id[:8] + "..." if self.app_id else "None",
            "api_key_length": len(self.api_key) if self.api_key else 0,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None
        }
    
    # Métodos de compatibilidad
    def add_latency_to_history(self, data: Dict) -> bool:
        try:
            if not self.enabled:
                return False
            
            pc_name = data.get('pc_name', '')
            device_id = self._generate_device_id(pc_name)
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            row = {
                "record_id": str(uuid.uuid4()),
                "device_id": device_id,
                "timestamp": ts,
                "latency_ms": str(data.get('latency', 0)),
                "cpu_percent": str(data.get('cpu_load_percent', 0)),
                "ram_percent": str(data.get('ram_percent', 0)),
                "temperature_c": str(data.get('temperature_c', 0)),
                "disk_percent": str(data.get('disk_percent', 0)),
                "status": str(data.get('status', 'online')),
                "extended_sensors": str(data.get('extended_sensors', ''))
            }
            
            result = self._make_safe_request("latency_history", "Add", [row])
            
            if result:
                self.last_sync_time = datetime.now()
                
            return result is not None
            
        except Exception:
            return False
    
    def add_alert(self, data: Dict, type_alert: str, msg: str, sev: str) -> bool:
        try:
            if not self.enabled:
                return False
            
            device_id = self._generate_device_id(data.get('pc_name', ''))
            row = {
                "alert_id": str(uuid.uuid4()),
                "device_id": device_id,
                "alert_type": str(type_alert),
                "severity": str(sev),
                "message": str(msg),
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "resolved": "false",
                "resolved_at": ""
            }
            
            result = self._make_safe_request("alerts", "Add", [row])
            return result is not None
            
        except Exception:
            return False
    
    # Aliases
    def sync_device_complete(self, data: Dict) -> bool:
        return self.get_or_create_device(data)[0]
    
    def upsert_device(self, data: Dict) -> bool:
        return self.get_or_create_device(data)[0]
    
    def add_latency_record(self, data: Dict) -> bool:
        return self.add_latency_to_history(data)
    
    def list_available_tables(self) -> List[str]:
        return list(self.table_status.keys())
