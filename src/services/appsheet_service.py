import os
import requests
import json
import hashlib
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
            logger.warning("AppSheetService deshabilitado - Configuración incompleta")
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService Conectado - App ID: {self.app_id[:10]}...")

        # Probar conexión inicial
        try:
            connection_ok = self._test_table_connection('devices')
            if connection_ok:
                logger.info("✅ Conexión inicial a AppSheet exitosa")
            else:
                logger.warning("⚠️  Conexión inicial a AppSheet falló")
        except Exception as e:
            logger.error(f"Error en conexión inicial: {e}")

    def _test_table_connection(self, table_name: str) -> bool:
        """Prueba conexión a una tabla específica"""
        try:
            if not self.enabled: 
                return False
                
            payload = {
                "Action": "Find", 
                "Properties": {
                    "Locale": "es-MX", 
                    "Top": 1
                }
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/{table_name}/Action",
                headers=self.headers, 
                json=payload, 
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Conexión a tabla '{table_name}' exitosa")
                return True
            else:
                logger.warning(f"⚠️  Conexión a tabla '{table_name}' falló: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error probando conexión a {table_name}: {e}")
            return False

    def test_history_connection(self) -> bool:
        """Prueba específica para la conexión con device_history"""
        try:
            if not self.enabled: 
                logger.warning("AppSheet deshabilitado")
                return False
            
            test_payload = {
                "Action": "Find",
                "Properties": {
                    "Locale": "es-MX",
                    "Top": 1
                }
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/device_history/Action",
                headers=self.headers,
                json=test_payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✅ Conexión a device_history OK")
                return True
            else:
                logger.error(f"❌ Error en device_history: {response.status_code} - {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"Error probando device_history: {e}")
            return False

    def generate_device_id(self, pc_name: str) -> str:
        """Genera un ID único para el dispositivo basado en el nombre del PC"""
        try:
            if not pc_name or not pc_name.strip():
                return "UNKNOWN_ID"
                
            pc_name = pc_name.strip()
            
            # Si ya comienza con MX_, usar esa parte
            if pc_name.upper().startswith("MX_"):
                parts = pc_name.split(' ')
                if len(parts) > 0:
                    return parts[0].strip().upper()
            
            # Generar hash MD5 consistente
            return hashlib.md5(pc_name.encode()).hexdigest()[:16].upper()
            
        except Exception as e:
            logger.error(f"Error generando device_id: {e}")
            return "ERROR_ID"

    def _make_safe_request(self, table: str, action: str, rows: List[Dict] = None) -> Optional[Any]:
        """Método seguro para hacer peticiones a AppSheet con logging detallado"""
        try:
            if not self.enabled: 
                logger.warning(f"AppSheet deshabilitado, saltando {action} en {table}")
                return None
            
            # Construir payload
            payload = {
                "Action": action, 
                "Properties": {
                    "Locale": "es-MX",
                    "Timezone": "Central Standard Time"
                }
            }
            
            if rows: 
                payload["Rows"] = rows
            
            logger.info(f"📤 Enviando a AppSheet - Tabla: {table}, Acción: {action}, Filas: {len(rows) if rows else 0}")
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            # Log detallado del request
            logger.debug(f"📋 Request URL: {url}")
            if rows:
                safe_rows = []
                for row in rows:
                    safe_row = row.copy()
                    # Ocultar datos sensibles
                    if 'api_key' in str(safe_row).lower() or 'key' in str(safe_row).lower():
                        for k in list(safe_row.keys()):
                            if 'key' in k.lower():
                                safe_row[k] = '***REDACTED***'
                    safe_rows.append(safe_row)
                logger.debug(f"📋 Request data (first row): {json.dumps(safe_rows[0] if safe_rows else {}, indent=2, ensure_ascii=False)}")
            
            # Hacer la petición
            response = requests.post(
                url,
                headers=self.headers, 
                json=payload, 
                timeout=30
            )
            
            logger.info(f"📥 Respuesta AppSheet - Status: {response.status_code}")
            
            if response.status_code == 200:
                try: 
                    result = response.json()
                    logger.info(f"✅ AppSheet {action} exitoso en {table}")
                    return result
                except Exception as e:
                    logger.warning(f"AppSheet no devolvió JSON: {e}, pero status es 200. Response: {response.text[:200]}")
                    return {"success": True}
            
            # Log detallado del error
            logger.error(f"❌ AppSheet Error {response.status_code}")
            logger.error(f"URL: {url}")
            logger.error(f"Response text: {response.text[:500]}")
            
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"⏰ Timeout en petición a AppSheet (tabla: {table})")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"🔌 Error de conexión con AppSheet")
            return None
        except Exception as e:
            logger.error(f"🔥 Error crítico en AppSheet request: {e}", exc_info=True)
            return None

    # --- MÉTODOS CORE ---

    def upsert_device(self, device_data: Dict) -> bool:
        """Crea o actualiza un dispositivo en AppSheet - IMPORTANTE: device_id es la referencia"""
        try:
            if not self.enabled: 
                return False
            
            pc_name = device_data.get('pc_name', '').strip()
            if not pc_name:
                logger.error("No se puede upsert dispositivo sin pc_name")
                return False
            
            # Generar device_id que será usado como referencia
            device_id = self.generate_device_id(pc_name)
            logger.info(f"🆔 Device ID generado para {pc_name}: {device_id}")
            
            # Asegurar datos mínimos
            unit = device_data.get('unit', 'General')
            ip = device_data.get('public_ip', device_data.get('ip', ''))
            status = device_data.get('status', 'online')
            
            row = {
                "device_id": device_id,  # Esta es la columna clave
                "pc_name": pc_name,
                "unit": unit,
                "public_ip": ip,
                "status": status,
                "updated_at": datetime.now(TZ_MX).isoformat()
            }
            
            logger.info(f"🔄 Upsert dispositivo en tabla 'devices': {pc_name} (ID: {device_id})")
            
            # Intentar Add (AppSheet maneja upsert automáticamente en muchos casos)
            result = self._make_safe_request("devices", "Add", [row])
            
            if result is not None:
                self.last_sync_time = datetime.now(TZ_MX)
                logger.info(f"✅ Dispositivo {pc_name} (ID: {device_id}) sincronizado en tabla devices")
                return True
            else:
                logger.error(f"❌ Falló upsert para {pc_name} en tabla devices")
                return False
                
        except Exception as e:
            logger.error(f"Error en upsert_device: {e}", exc_info=True)
            return False

    def add_history_entry(self, log_data: Dict) -> bool:
        """
        Guarda ficha en device_history asegurando que el device_id existe en devices primero.
        device_id es una REFERENCIA a la tabla devices.
        """
        try:
            if not self.enabled: 
                logger.warning("AppSheet deshabilitado, no se guardará ficha")
                return False
            
            # Log detallado de entrada
            logger.info(f"📝 Recibiendo ficha para bitácora")
            logger.debug(f"📋 Datos recibidos: {json.dumps(log_data, indent=2, ensure_ascii=False)}")
            
            device_name = log_data.get('device_name') or log_data.get('pc_name')
            if not device_name:
                logger.error("❌ Error Bitácora: Falta nombre del dispositivo")
                return False

            logger.info(f"🔧 Procesando ficha para dispositivo: {device_name}")
            
            # 1. IMPORTANTE: Asegurar que el dispositivo existe en la tabla devices primero
            # Esto es CRÍTICO porque device_id es una referencia
            logger.info(f"🔄 Verificando/Creando dispositivo en tabla 'devices': {device_name}")
            
            device_created = self.upsert_device({
                "pc_name": device_name,
                "unit": log_data.get('unit', log_data.get('unit_snapshot', 'General')),
                "status": 'online',
                "public_ip": log_data.get('public_ip', '')
            })
            
            if not device_created:
                logger.error("❌ No se pudo crear/verificar dispositivo en tabla devices. No se puede crear referencia.")
                return False
            
            # 2. Generar device_id (debe ser IDENTICO al usado en la tabla devices)
            device_id = self.generate_device_id(device_name)
            logger.info(f"🆔 Device ID para referencia: {device_id}")
            
            # 3. Preparar timestamp
            timestamp = log_data.get('timestamp')
            if not timestamp:
                timestamp = datetime.now(TZ_MX).isoformat()
            
            # 4. Preparar datos para device_history con los campos EXACTOS de tu tabla
            component = log_data.get('what', log_data.get('component', 'General'))
            
            # Validar componentes (basado en lo que me dijiste)
            valid_components = ['NUC', 'SD300', 'UPS', 'MODULO', 'COMPONENTES', 'TELTONIKA', 'General', 'Otro']
            if component not in valid_components:
                logger.warning(f"⚠️  Componente '{component}' no está en la lista de válidos, usando 'General'")
                component = 'General'
            
            history_row = {
                "device_id": device_id,  # REFERENCIA a la tabla devices
                "timestamp": timestamp,
                "requester": log_data.get('req', log_data.get('requester', 'Sistema')),
                "executor": log_data.get('exec', log_data.get('executor', 'Pendiente')),
                "action_type": log_data.get('action', log_data.get('action_type', 'Mantenimiento')),
                "component": component,
                "description": log_data.get('desc', log_data.get('description', '')),
                "is_resolved": log_data.get('solved', log_data.get('is_resolved', False)),
                "unit_snapshot": log_data.get('unit', log_data.get('unit_snapshot', 'General'))
            }
            
            # Convertir booleanos a strings "TRUE"/"FALSE" para AppSheet Yes/No
            if isinstance(history_row["is_resolved"], bool):
                history_row["is_resolved"] = "TRUE" if history_row["is_resolved"] else "FALSE"
            elif isinstance(history_row["is_resolved"], str):
                resolved_lower = history_row["is_resolved"].lower()
                history_row["is_resolved"] = "TRUE" if resolved_lower == "true" or resolved_lower == "yes" or resolved_lower == "si" else "FALSE"
            
            # Asegurar que todos los campos sean strings
            for key, value in history_row.items():
                if value is None:
                    history_row[key] = ""
                elif not isinstance(value, str):
                    history_row[key] = str(value)
            
            logger.info(f"💾 Guardando Ficha en 'device_history' para {device_name}...")
            logger.info(f"📋 Datos a guardar en device_history:")
            logger.info(json.dumps(history_row, indent=2, ensure_ascii=False))
            
            # 5. Guardar en device_history
            res_hist = self._make_safe_request("device_history", "Add", [history_row])
            
            if res_hist is not None:
                logger.info(f"✅ Ficha guardada exitosamente en device_history")
                logger.debug(f"📤 Respuesta AppSheet device_history: {json.dumps(res_hist, indent=2, ensure_ascii=False)}")
                
                # 6. Lógica de Baja/Reactivación (actualizar tabla devices si es necesario)
                action = log_data.get('action', '').lower()
                if 'baja' in action or 'retiro' in action:
                    logger.info(f"📉 Marcando dispositivo {device_id} como offline por baja")
                    self.update_device_status(device_id, 'offline')
                elif 'instalación' in action or 'renovación' in action or 'activación' in action:
                    logger.info(f"📈 Marcando dispositivo {device_id} como online por instalación/renovación")
                    self.update_device_status(device_id, 'online')
                
                return True
            else:
                logger.error("❌ AppSheet rechazó la ficha en device_history")
                logger.error("⚠️  Posibles causas:")
                logger.error("   1. El device_id no existe en la tabla devices (falta referencia)")
                logger.error("   2. Error en el formato de datos")
                logger.error("   3. Permisos insuficientes")
                return False
                    
        except Exception as e:
            logger.error(f"🔥 Error crítico en add_history_entry: {e}", exc_info=True)
            return False

    def update_device_status(self, device_id: str, status: str):
        """Actualiza el estado de un dispositivo en la tabla devices"""
        try:
            if not self.enabled or not device_id:
                logger.warning("No se puede actualizar estado: AppSheet deshabilitado o sin device_id")
                return
                
            row = {
                "device_id": device_id,  # Usar el mismo device_id de referencia
                "status": status, 
                "updated_at": datetime.now(TZ_MX).isoformat()
            }
            
            logger.info(f"🔄 Actualizando estado de dispositivo {device_id} a {status}")
            
            result = self._make_safe_request("devices", "Edit", [row])
            if result:
                logger.info(f"✅ Estado de {device_id} actualizado a {status} en tabla devices")
            else:
                logger.warning(f"⚠️  No se pudo actualizar estado de {device_id} en tabla devices")
                
        except Exception as e:
            logger.error(f"Error en update_device_status: {e}")

    def get_full_history(self) -> List[Dict]:
        """Obtiene todo el historial de bitácora"""
        try:
            if not self.enabled: 
                logger.info("AppSheet deshabilitado, retornando lista vacía")
                return []
            
            logger.info("📋 Solicitando historial completo de device_history...")
            
            # Hacer una petición con Top para limitar resultados
            payload = {
                "Action": "Find",
                "Properties": {
                    "Locale": "es-MX",
                    "Top": 100
                }
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/device_history/Action",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Historial obtenido de device_history. Status: 200")
                
                # AppSheet puede devolver diferentes formatos
                rows = []
                if isinstance(data, list):
                    rows = data
                    logger.info(f"✅ Historial obtenido (formato lista): {len(rows)} registros")
                elif isinstance(data, dict):
                    if 'Rows' in data:
                        rows = data['Rows']
                        logger.info(f"✅ Historial obtenido (formato Rows): {len(rows)} registros")
                    elif 'data' in data:
                        rows = data['data']
                        logger.info(f"✅ Historial obtenido (formato data): {len(rows)} registros")
                    else:
                        # Intentar extraer cualquier lista del diccionario
                        for key, value in data.items():
                            if isinstance(value, list):
                                rows = value
                                logger.info(f"✅ Historial obtenido (clave '{key}'): {len(rows)} registros")
                                break
                
                if rows:
                    logger.info(f"📊 Primer registro: device_id={rows[0].get('device_id', 'N/A')}, action={rows[0].get('action_type', 'N/A')}")
                    
                    # Intentar ordenar por timestamp descendente
                    try:
                        def get_sort_key(item):
                            ts = item.get('timestamp', '')
                            try:
                                # Intentar parsear diferentes formatos de fecha
                                if 'T' in ts:
                                    return datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                else:
                                    # Intentar otros formatos comunes
                                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f']:
                                        try:
                                            return datetime.strptime(ts, fmt)
                                        except:
                                            continue
                                    return datetime.min
                            except Exception as e:
                                logger.warning(f"Error parseando timestamp '{ts}': {e}")
                                return datetime.min
                        
                        sorted_data = sorted(rows, key=get_sort_key, reverse=True)
                        logger.info(f"📊 Total registros ordenados: {len(sorted_data)}")
                        return sorted_data
                    except Exception as e:
                        logger.error(f"Error ordenando datos: {e}")
                        return rows
                else:
                    logger.warning("⚠️  No se encontraron registros en device_history")
                    return []
                    
            else:
                logger.error(f"❌ Error HTTP {response.status_code} al obtener historial")
                logger.error(f"Response: {response.text[:500]}")
                return []
                
        except Exception as e:
            logger.error(f"Error en get_full_history: {e}", exc_info=True)
            return []
