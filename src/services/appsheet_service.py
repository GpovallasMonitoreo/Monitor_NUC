import os
import requests
import json
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
import traceback

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

TZ_MX = ZoneInfo("America/Mexico_City")
logger = logging.getLogger(__name__)

class AppSheetService:
    """
    Servicio AppSheet mejorado con mejor manejo de errores y conexión.
    """
    
    def __init__(self):
        # Configuración de logging para debug
        logging.basicConfig(level=logging.DEBUG)
        
        # 1. Obtener y limpiar credenciales
        raw_key = os.getenv('APPSHEET_API_KEY', '').strip()
        raw_id = os.getenv('APPSHEET_APP_ID', '').strip()
        raw_enabled = os.getenv('APPSHEET_ENABLED', 'true').strip().lower()
        
        self.api_key = raw_key
        self.app_id = raw_id
        self.base_url = "https://api.appsheet.com/api/v2"
        
        # Debug de credenciales
        logger.info(f"🔍 Credenciales cargadas:")
        logger.info(f"   APPSHEET_ENABLED: {raw_enabled}")
        logger.info(f"   API_KEY length: {len(self.api_key)}")
        logger.info(f"   API_KEY (primeros 10): {self.api_key[:10] if self.api_key else 'None'}...")
        logger.info(f"   APP_ID: {self.app_id[:20] if self.app_id else 'None'}...")
        
        # 2. Validar si está habilitado
        self.enabled = raw_enabled in ['true', '1', 'yes', 'on']
        
        if not self.enabled:
            logger.warning("⚠️ AppSheetService DESHABILITADO por configuración")
            self.connection_status = "disabled"
            return
            
        # 3. Validar credenciales
        if not self.api_key or len(self.api_key) < 20:
            logger.error("❌ API KEY inválida o demasiado corta")
            self.enabled = False
            self.connection_status = "invalid_key"
            return
            
        if not self.app_id or len(self.app_id) < 10:
            logger.error("❌ APP ID inválido o demasiado corto")
            self.enabled = False
            self.connection_status = "invalid_app_id"
            return
            
        # 4. Headers para requests
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        
        self.last_sync_time = None
        self.connection_status = "disconnected"
        
        # 5. Test inicial de conexión
        self._test_initial_connection()
        
    def _test_initial_connection(self):
        """Test de conexión inicial a AppSheet"""
        try:
            logger.info("🔌 Probando conexión a AppSheet...")
            
            # Primero, intentamos obtener la lista de tablas
            test_payload = {
                "Action": "GetTableNames",
                "Properties": {
                    "Locale": "es-MX"
                }
            }
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/Action"
            logger.debug(f"URL de prueba: {url}")
            
            response = requests.post(
                url,
                headers=self.headers,
                json=test_payload,
                timeout=15
            )
            
            logger.info(f"📡 Respuesta de test: Status {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, list):
                        tables = data
                    elif isinstance(data, dict) and 'TableNames' in data:
                        tables = data['TableNames']
                    else:
                        tables = []
                    
                    logger.info(f"✅ Conexión exitosa. Tablas disponibles: {tables}")
                    self.connection_status = "connected"
                    self.enabled = True
                    self.last_sync_time = datetime.now(TZ_MX)
                    
                except json.JSONDecodeError:
                    logger.warning("⚠️ Respuesta 200 pero no es JSON válido")
                    logger.debug(f"Respuesta raw: {response.text[:200]}")
                    self.connection_status = "connected_but_invalid_json"
                    self.enabled = True
            else:
                logger.error(f"❌ Error en test de conexión: {response.status_code}")
                logger.error(f"Respuesta: {response.text[:500]}")
                self.connection_status = f"error_{response.status_code}"
                self.enabled = False
                
        except requests.exceptions.Timeout:
            logger.error("⏰ Timeout al conectar con AppSheet")
            self.connection_status = "timeout"
            self.enabled = False
            
        except requests.exceptions.ConnectionError:
            logger.error("🔌 Error de conexión a AppSheet (no se pudo establecer conexión)")
            self.connection_status = "connection_error"
            self.enabled = False
            
        except Exception as e:
            logger.error(f"🔥 Error inesperado en test de conexión: {str(e)}")
            logger.error(traceback.format_exc())
            self.connection_status = f"error_{type(e).__name__}"
            self.enabled = False
    
    def _make_safe_request(self, table: str, action: str, rows: List[Dict] = None, 
                          properties: Dict = None, max_retries: int = 2) -> Optional[Any]:
        """Envía petición HTTP con reintentos y manejo robusto de errores"""
        
        if not self.enabled or self.connection_status != "connected":
            logger.warning(f"Servicio no habilitado para {table}.{action}")
            return None
            
        for attempt in range(max_retries + 1):
            try:
                # Preparar propiedades
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
                    # Convertir todos los valores a string
                    safe_rows = []
                    for row in rows:
                        safe_row = {}
                        for key, value in row.items():
                            if value is None:
                                safe_row[key] = ""
                            else:
                                safe_row[key] = str(value).strip()
                        safe_rows.append(row)
                    payload["Rows"] = safe_rows
                
                # URL final
                url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
                
                logger.debug(f"📤 Enviando a {table}.{action} (intento {attempt + 1})")
                logger.debug(f"Payload keys: {list(payload.keys())}")
                if rows:
                    logger.debug(f"Número de filas: {len(rows)}")
                    logger.debug(f"Primera fila keys: {list(rows[0].keys())}")
                
                # Enviar request
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
                
                # Actualizar última sincronización
                self.last_sync_time = datetime.now(TZ_MX)
                
                logger.debug(f"📥 Respuesta status: {response.status_code}")
                
                # Manejar respuesta
                if response.status_code == 200:
                    if not response.text or response.text.strip() == "":
                        logger.info(f"✅ {table}.{action}: Éxito (respuesta vacía)")
                        return {"status": "success", "message": "empty_response"}
                    
                    try:
                        result = response.json()
                        logger.info(f"✅ {table}.{action}: Éxito")
                        return result
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ {table}.{action}: JSON inválido, retornando texto")
                        return {"status": "success", "raw_text": response.text}
                
                elif response.status_code == 401:
                    logger.error(f"🔐 {table}.{action}: Error 401 - API KEY inválida o expirada")
                    self.connection_status = "unauthorized"
                    self.enabled = False
                    return None
                    
                elif response.status_code == 404:
                    logger.error(f"🔍 {table}.{action}: Error 404 - Tabla '{table}' no encontrada")
                    # Listar tablas disponibles para debug
                    self._list_available_tables()
                    return None
                    
                else:
                    logger.error(f"❌ {table}.{action}: Error {response.status_code}")
                    logger.error(f"Respuesta: {response.text[:500]}")
                    
                    # Reintentar si es error del servidor
                    if response.status_code >= 500 and attempt < max_retries:
                        logger.info(f"Reintentando en 2 segundos...")
                        import time
                        time.sleep(2)
                        continue
                        
                    return None
                    
            except requests.exceptions.Timeout:
                logger.error(f"⏰ {table}.{action}: Timeout")
                if attempt < max_retries:
                    logger.info("Reintentando después de timeout...")
                    continue
                return None
                
            except requests.exceptions.ConnectionError:
                logger.error(f"🔌 {table}.{action}: Error de conexión")
                self.connection_status = "connection_error"
                if attempt < max_retries:
                    logger.info("Reintentando después de error de conexión...")
                    import time
                    time.sleep(3)
                    continue
                return None
                
            except Exception as e:
                logger.error(f"🔥 {table}.{action}: Excepción - {str(e)}")
                logger.error(traceback.format_exc())
                return None
        
        return None
    
    def _list_available_tables(self):
        """Lista todas las tablas disponibles en la app"""
        try:
            payload = {
                "Action": "GetTableNames",
                "Properties": {"Locale": "es-MX"}
            }
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/Action"
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    logger.info(f"📊 Tablas disponibles: {data}")
                elif isinstance(data, dict) and 'TableNames' in data:
                    logger.info(f"📊 Tablas disponibles: {data['TableNames']}")
                else:
                    logger.info(f"📊 Respuesta de tablas: {data}")
            else:
                logger.error(f"Error al obtener tablas: {response.status_code}")
        except Exception as e:
            logger.error(f"Error al listar tablas: {e}")
    
    def generate_device_id(self, pc_name: str) -> str:
        """Genera ID consistente."""
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
    
    # --- MÉTODOS DE ESCRITURA ---
    
    def get_or_create_device(self, device_data: Dict) -> tuple:
        """
        Crea o actualiza un dispositivo.
        Returns: (success: bool, device_id: str, was_created: bool)
        """
        try:
            if not self.enabled:
                return False, None, False
                
            pc_name = str(device_data.get('pc_name', '')).strip()
            if not pc_name:
                logger.warning("No se puede crear dispositivo sin pc_name")
                return False, None, False
            
            device_id = self.generate_device_id(pc_name)
            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            # Primero, verificar si ya existe
            logger.info(f"Buscando dispositivo: {device_id} ({pc_name})")
            
            row = {
                "device_id": device_id,
                "pc_name": pc_name,
                "unit": str(device_data.get('unit', 'General')),
                "public_ip": str(device_data.get('public_ip', device_data.get('ip', ''))),
                "last_known_location": str(device_data.get('locName', pc_name)),
                "updated_at": ts,
                "created_at": ts
            }
            
            # Intentar añadir (Add maneja duplicados si configurado en AppSheet)
            res = self._make_safe_request("devices", "Add", [row])
            
            if res:
                logger.info(f"✅ Dispositivo {device_id} sincronizado")
                return True, device_id, True
            else:
                logger.warning(f"⚠️ No se pudo sincronizar dispositivo {device_id}")
                return False, device_id, False
                
        except Exception as e:
            logger.error(f"Error en get_or_create_device: {e}")
            logger.error(traceback.format_exc())
            return False, None, False
    
    def add_history_entry(self, log_data: Dict) -> bool:
        """Añade una entrada al historial"""
        try:
            if not self.enabled:
                return False
                
            pc_name = log_data.get('pc_name') or log_data.get('device_name', '')
            if not pc_name:
                logger.warning("No se puede añadir historial sin pc_name")
                return False
            
            # Obtener/crear dispositivo primero
            device_id = self.generate_device_id(pc_name)
            
            # Intentar crear dispositivo si no existe
            device_success, _, _ = self.get_or_create_device({
                "pc_name": pc_name,
                "unit": log_data.get('unit', 'General')
            })
            
            if not device_success:
                logger.warning(f"Dispositivo {pc_name} no pudo crearse, pero continuamos con historial")
            
            # Crear entrada de historial
            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            row = {
                "history_id": str(uuid.uuid4()),
                "device_id": device_id,
                "action": str(log_data.get('action', 'Info')),
                "what": str(log_data.get('what', 'General')),
                "desc": str(log_data.get('desc', 'NA')),
                "exec": str(log_data.get('exec', 'Sistema')),
                "solved": str(log_data.get('solved', 'true')).lower(),
                "unit": str(log_data.get('unit', 'General')),
                "timestamp": ts
            }
            
            logger.info(f"Añadiendo historial para {device_id}: {row['action']} - {row['desc'][:50]}...")
            
            res = self._make_safe_request("device_history", "Add", [row])
            
            success = res is not None
            if success:
                logger.info(f"✅ Historial añadido para {device_id}")
            else:
                logger.warning(f"⚠️ No se pudo añadir historial para {device_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error en add_history_entry: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def add_latency_to_history(self, data: Dict) -> bool:
        """Añade registro de latencia"""
        try:
            if not self.enabled:
                return False
                
            pc_name = data.get('pc_name', '')
            device_id = self.generate_device_id(pc_name)
            
            row = {
                "record_id": str(uuid.uuid4()),
                "device_id": device_id,
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "latency_ms": str(data.get('latency', 0)),
                "cpu_load": str(data.get('cpu_load_percent', 0)),
                "ram_usage": str(data.get('ram_percent', 0)),
                "status": str(data.get('status', 'online'))
            }
            
            res = self._make_safe_request("latency_history", "Add", [row])
            return res is not None
            
        except Exception as e:
            logger.error(f"Error en add_latency_to_history: {e}")
            return False
    
    def add_alert(self, data: Dict, type_alert: str, msg: str, sev: str) -> bool:
        """Añade una alerta"""
        try:
            if not self.enabled:
                return False
                
            pc_name = data.get('pc_name', 'Unknown')
            device_id = self.generate_device_id(pc_name)
            
            row = {
                "alert_id": str(uuid.uuid4()),
                "device_id": device_id,
                "alert_type": str(type_alert),
                "severity": str(sev),
                "message": str(msg),
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S'),
                "resolved": "false"
            }
            
            res = self._make_safe_request("alerts", "Add", [row])
            
            if res:
                logger.warning(f"🚨 Alerta {sev} añadida: {msg[:50]}...")
                
            return res is not None
            
        except Exception as e:
            logger.error(f"Error en add_alert: {e}")
            return False
    
    # --- MÉTODOS DE LECTURA ---
    
    def get_full_history(self, limit: int = 50) -> List[Dict]:
        """Obtiene todo el historial"""
        try:
            if not self.enabled:
                return []
                
            res = self._make_safe_request(
                "device_history", 
                "Find", 
                properties={"Top": limit, "OrderBy": "[timestamp] DESC"}
            )
            
            if res and isinstance(res, list):
                return res[:limit]
            elif res and isinstance(res, dict) and 'Rows' in res:
                return res['Rows'][:limit]
            elif res and isinstance(res, dict) and isinstance(res.get('rows'), list):
                return res['rows'][:limit]
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
                
            dev_id = self.generate_device_id(pc_name)
            
            # Usar selector de AppSheet
            selector = f"Filter(device_history, [device_id] = \"{dev_id}\")"
            
            res = self._make_safe_request(
                "device_history", 
                "Find", 
                properties={
                    "Selector": selector,
                    "OrderBy": "[timestamp] DESC"
                }
            )
            
            if res and isinstance(res, list):
                return res
            elif res and isinstance(res, dict) and 'Rows' in res:
                return res['Rows']
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error en get_history_for_device: {e}")
            return []
    
    def get_status_info(self) -> Dict:
        """Obtiene información de estado del servicio"""
        return {
            "enabled": self.enabled,
            "connection_status": self.connection_status,
            "last_sync": str(self.last_sync_time) if self.last_sync_time else "Nunca",
            "app_id_preview": self.app_id[:10] + "..." if self.app_id else "None",
            "api_key_preview": self.api_key[:5] + "..." if self.api_key else "None"
        }
    
    def get_system_stats(self) -> Dict:
        """Obtiene estadísticas del sistema"""
        return {
            "status": "ok" if self.enabled else "error",
            "mode": "AppSheet",
            "connection": self.connection_status,
            "tables": ["devices", "device_history", "latency_history", "alerts"]
        }
    
    # --- MÉTODOS DE DIAGNÓSTICO ---
    
    def run_diagnostic(self) -> Dict:
        """Ejecuta diagnóstico completo del servicio"""
        diagnostic = {
            "timestamp": datetime.now(TZ_MX).isoformat(),
            "service_status": self.get_status_info(),
            "tests": {}
        }
        
        # Test 1: Listar tablas
        try:
            test_payload = {"Action": "GetTableNames", "Properties": {"Locale": "es-MX"}}
            url = f"{self.base_url}/apps/{self.app_id}/tables/Action"
            response = requests.post(url, headers=self.headers, json=test_payload, timeout=10)
            diagnostic["tests"]["list_tables"] = {
                "status_code": response.status_code,
                "success": response.status_code == 200
            }
        except Exception as e:
            diagnostic["tests"]["list_tables"] = {"error": str(e), "success": False}
        
        # Test 2: Insertar dispositivo de prueba
        test_device = {
            "pc_name": f"TEST_{datetime.now().strftime('%H%M%S')}",
            "unit": "Diagnóstico",
            "public_ip": "127.0.0.1"
        }
        success, dev_id, created = self.get_or_create_device(test_device)
        diagnostic["tests"]["create_device"] = {
            "success": success,
            "device_id": dev_id,
            "created": created
        }
        
        return diagnostic
    
    # --- ALIASES para compatibilidad ---
    
    def sync_device_complete(self, data: Dict) -> bool:
        return self.get_or_create_device(data)[0]
    
    def upsert_device(self, data: Dict) -> bool:
        return self.get_or_create_device(data)[0]
    
    def add_latency_record(self, data: Dict) -> bool:
        return self.add_latency_to_history(data)
    
    def list_available_tables(self) -> List[str]:
        return ["devices", "device_history", "latency_history", "alerts"]
