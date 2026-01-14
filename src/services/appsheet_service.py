# src/services/appsheet_service.py
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
    """Servicio AppSheet adaptado a tu estructura exacta de tablas"""
    
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY', '').strip()
        self.app_id = os.getenv('APPSHEET_APP_ID', '').strip()
        enabled = os.getenv('APPSHEET_ENABLED', 'true').strip().lower()
        
        self.enabled = enabled in ['true', '1', 'yes', 'on'] and self.api_key and self.app_id
        self.base_url = "https://api.appsheet.com/api/v2"
        self.headers = {
            'Content-Type': 'application/json', 
            'ApplicationAccessKey': self.api_key
        }
        
        # Estado de conexión por tabla
        self.table_status = {}
        self.last_sync_time = None
        
        logger.info(f"AppSheet Service: {'ENABLED' if self.enabled else 'DISABLED'}")
        
        if self.enabled:
            self._test_all_tables()
    
    def _test_all_tables(self):
        """Prueba conexión con todas las tablas"""
        tables_to_test = [
            "devices",
            "device_history", 
            "latency_history",
            "alerts"
        ]
        
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
                
                # Si hay resultado, mostrar columnas
                if result:
                    columns = self._extract_columns_from_result(result)
                    if columns:
                        logger.info(f"     Columnas encontradas: {', '.join(columns[:5])}...")
                
            except Exception as e:
                self.table_status[table_name] = False
                logger.info(f"  ❌ Tabla '{table_name}': Error - {str(e)[:50]}")
    
    def _extract_columns_from_result(self, result: Any) -> List[str]:
        """Extrae nombres de columnas del resultado"""
        try:
            if isinstance(result, list) and len(result) > 0:
                return list(result[0].keys())
            elif isinstance(result, dict) and 'Rows' in result and len(result['Rows']) > 0:
                return list(result['Rows'][0].keys())
        except:
            pass
        return []
    
    def _make_safe_request(self, table: str, action: str, rows: List[Dict] = None, 
                          properties: Dict = None) -> Optional[Any]:
        """Envía petición HTTP con manejo de errores"""
        if not self.enabled:
            logger.warning(f"AppSheet deshabilitado - No se envió {table}.{action}")
            return None
        
        try:
            # Configurar propiedades básicas
            final_props = {
                "Locale": "es-MX",
                "Timezone": "Central Standard Time"
            }
            if properties:
                final_props.update(properties)
            
            # Preparar payload
            payload = {
                "Action": action,
                "Properties": final_props
            }
            
            if rows:
                # Asegurar que todos los valores sean strings
                safe_rows = []
                for row in rows:
                    safe_row = {}
                    for key, value in row.items():
                        if value is None:
                            safe_row[key] = ""
                        else:
                            safe_row[key] = str(value)
                    safe_rows.append(safe_row)
                payload["Rows"] = safe_rows
            
            # Construir URL
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            logger.debug(f"📤 AppSheet: {table}.{action}")
            
            # Enviar request
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            # Procesar respuesta
            if response.status_code == 200:
                if not response.text or response.text.strip() == "":
                    logger.info(f"✅ {table}.{action}: Éxito (respuesta vacía)")
                    return {"status": "success", "message": "empty_response"}
                
                try:
                    result = response.json()
                    logger.info(f"✅ {table}.{action}: Éxito")
                    return result
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ {table}.{action}: Respuesta no es JSON")
                    return {"status": "success", "raw": response.text}
            
            else:
                logger.error(f"❌ {table}.{action}: Error {response.status_code}")
                
                if response.status_code == 404:
                    logger.error(f"   ⚠️ Tabla '{table}' no existe")
                elif response.status_code == 401:
                    logger.error("   🔐 API Key inválida o expirada")
                
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"⏰ {table}.{action}: Timeout")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"🔌 {table}.{action}: Error de conexión")
            return None
        except Exception as e:
            logger.error(f"🔥 {table}.{action}: Excepción - {str(e)}")
            return None
    
    # ==================== MÉTODOS PARA CADA TABLA ====================
    
    def get_or_create_device(self, device_data: Dict) -> tuple:
        """Crea o actualiza un dispositivo en tabla 'devices'"""
        try:
            if not self.enabled:
                return False, None, False
            
            pc_name = str(device_data.get('pc_name', '')).strip()
            if not pc_name:
                logger.warning("No se puede crear dispositivo sin pc_name")
                return False, None, False
            
            # Generar ID consistente
            device_id = self._generate_device_id(pc_name)
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # ¡COLUMNAS EXACTAS DE TU TABLA 'devices'!
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
            
            logger.info(f"Creando dispositivo: {device_id} ({pc_name})")
            
            # Intentar añadir
            result = self._make_safe_request("devices", "Add", [row])
            
            if result:
                logger.info(f"✅ Dispositivo {device_id} creado/existente")
                self.last_sync_time = datetime.now()
                return True, device_id, True
            else:
                logger.warning(f"⚠️ No se pudo crear dispositivo {device_id}")
                return False, device_id, False
                
        except Exception as e:
            logger.error(f"Error en get_or_create_device: {e}")
            return False, None, False
    
    def add_history_entry(self, log_data: Dict) -> bool:
        """Añade una entrada al historial en tabla 'device_history'"""
        try:
            if not self.enabled:
                return False
            
            pc_name = log_data.get('pc_name') or log_data.get('device_name', '')
            if not pc_name:
                logger.warning("No se puede añadir historial sin pc_name")
                return False
            
            device_id = self._generate_device_id(pc_name)
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # ¡COLUMNAS EXACTAS DE TU TABLA 'device_history'!
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
            
            logger.info(f"Añadiendo historial: {device_id} - {row['action']}")
            
            result = self._make_safe_request("device_history", "Add", [row])
            
            if result:
                logger.info(f"✅ Historial añadido para {device_id}")
                self.last_sync_time = datetime.now()
            else:
                logger.warning(f"⚠️ No se pudo añadir historial para {device_id}")
                
            return result is not None
            
        except Exception as e:
            logger.error(f"Error en add_history_entry: {e}")
            return False
    
    def add_latency_to_history(self, data: Dict) -> bool:
        """Añade registro de latencia en tabla 'latency_history'"""
        try:
            if not self.enabled:
                return False
            
            pc_name = data.get('pc_name', '')
            device_id = self._generate_device_id(pc_name)
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # ¡COLUMNAS EXACTAS DE TU TABLA 'latency_history'!
            row = {
                "record_id": str(uuid.uuid4()),
                "device_id": device_id,
                "timestamp": ts,
                "latency_ms": str(data.get('latency', 0)),
                "cpu_percent": str(data.get('cpu_load_percent', data.get('cpu_percent', 0))),
                "ram_percent": str(data.get('ram_percent', 0)),
                "temperature_c": str(data.get('temperature_c', 0)),
                "disk_percent": str(data.get('disk_percent', 0)),
                "status": str(data.get('status', 'online')),
                "extended_sensors": str(data.get('extended_sensors', ''))
            }
            
            logger.info(f"Añadiendo latencia: {device_id} - {row['latency_ms']}ms")
            
            result = self._make_safe_request("latency_history", "Add", [row])
            
            if result:
                self.last_sync_time = datetime.now()
                
            return result is not None
            
        except Exception as e:
            logger.error(f"Error en add_latency_to_history: {e}")
            return False
    
    def add_alert(self, data: Dict, type_alert: str, msg: str, sev: str) -> bool:
        """Añade una alerta en tabla 'alerts'"""
        try:
            if not self.enabled:
                return False
            
            pc_name = data.get('pc_name', 'Unknown')
            device_id = self._generate_device_id(pc_name)
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # ¡COLUMNAS EXACTAS DE TU TABLA 'alerts'!
            row = {
                "alert_id": str(uuid.uuid4()),
                "device_id": device_id,
                "alert_type": str(type_alert),
                "severity": str(sev),
                "message": str(msg),
                "timestamp": ts,
                "resolved": "false",
                "resolved_at": ""
            }
            
            logger.warning(f"🚨 Añadiendo alerta {sev}: {type_alert} - {msg[:50]}...")
            
            result = self._make_safe_request("alerts", "Add", [row])
            
            if result:
                logger.warning(f"✅ Alerta registrada para {device_id}")
                self.last_sync_time = datetime.now()
                
            return result is not None
            
        except Exception as e:
            logger.error(f"Error en add_alert: {e}")
            return False
    
    # ==================== MÉTODOS AUXILIARES ====================
    
    def _generate_device_id(self, pc_name: str) -> str:
        """Genera ID consistente para dispositivos"""
        try:
            if not pc_name:
                return "UNKNOWN_" + str(uuid.uuid4())[:8]
            
            clean = pc_name.strip().upper()
            
            # Si ya tiene formato MX_XXXX, úsalo
            if clean.startswith("MX_") and len(clean) > 4:
                parts = clean.split(' ')
                if len(parts) > 0:
                    return parts[0].strip()
            
            # Generar hash consistente
            hash_obj = hashlib.md5(clean.encode())
            return f"HASH_{hash_obj.hexdigest()[:10].upper()}"
            
        except Exception:
            return "ERROR_" + str(uuid.uuid4())[:8]
    
    # ==================== MÉTODOS DE LECTURA ====================
    
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
    
    def get_history_for_device(self, pc_name: str) -> List[Dict]:
        """Obtiene historial para un dispositivo específico"""
        try:
            if not self.enabled:
                return []
            
            dev_id = self._generate_device_id(pc_name)
            selector = f"Filter(device_history, [device_id] = \"{dev_id}\")"
            
            result = self._make_safe_request(
                "device_history", 
                "Find", 
                properties={
                    "Selector": selector,
                    "OrderBy": "[timestamp] DESC",
                    "Top": 100
                }
            )
            
            if result and isinstance(result, list):
                return result
            elif result and isinstance(result, dict) and 'Rows' in result:
                return result['Rows']
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error en get_history_for_device: {e}")
            return []
    
    def get_status_info(self) -> Dict:
        """Obtiene información de estado detallada - VERSIÓN CORREGIDA"""
        is_connected = any(self.table_status.values()) if self.table_status else False
        
        return {
            "enabled": self.enabled,  # ¡BOOLEANO, no string!
            "connection_status": "connected" if is_connected else "disconnected",
            "tables": self.table_status,
            "has_credentials": bool(self.api_key and self.app_id),
            "app_id": self.app_id,
            "app_id_preview": self.app_id[:8] + "..." if self.app_id else "None",
            "api_key_length": len(self.api_key) if self.api_key else 0,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None
        }
    
    def get_system_stats(self) -> Dict:
        """Estadísticas del sistema - VERSIÓN CORREGIDA"""
        is_connected = any(self.table_status.values()) if self.table_status else False
        
        return {
            "status": "ok" if self.enabled and is_connected else "error",
            "mode": "AppSheet",
            "connection": "connected" if is_connected else "disconnected",
            "tables_connected": sum(1 for v in self.table_status.values() if v) if self.table_status else 0,
            "total_tables": len(self.table_status) if self.table_status else 0,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else "Nunca"
        }
    
    # ==================== MÉTODOS DE COMPATIBILIDAD ====================
    
    def _test_table_connection(self, table_name):
        """Método legacy para compatibilidad"""
        return self.table_status.get(table_name, False)
    
    def test_history_connection(self):
        """Método legacy para compatibilidad"""
        return self.table_status.get('device_history', False)
    
    # ==================== ALIASES PARA COMPATIBILIDAD ====================
    
    def sync_device_complete(self, data: Dict) -> bool:
        return self.get_or_create_device(data)[0]
    
    def upsert_device(self, data: Dict) -> bool:
        return self.get_or_create_device(data)[0]
    
    def add_latency_record(self, data: Dict) -> bool:
        return self.add_latency_to_history(data)
    
    def list_available_tables(self) -> List[str]:
        return list(self.table_status.keys())
