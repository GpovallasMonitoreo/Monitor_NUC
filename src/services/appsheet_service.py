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
            
            logger.debug(f"📤 AppSheet Request: {table}.{action}")
            
            response = requests.post(
                url,
                headers=self.headers, 
                json=payload, 
                timeout=30
            )
            
            logger.debug(f"📥 AppSheet Response: {response.status_code}")
            
            if response.status_code == 200:
                try: 
                    result = response.json()
                    return result
                except Exception as e:
                    logger.debug(f"AppSheet no devolvió JSON: {response.text[:100]}")
                    return {"success": True, "raw_text": response.text}
            
            logger.error(f"❌ AppSheet Error {response.status_code}: {response.text[:200]}")
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"⏰ Timeout en petición a AppSheet (tabla: {table})")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"🔌 Error de conexión con AppSheet")
            return None
        except Exception as e:
            logger.error(f"Error en petición AppSheet: {e}")
            return None

    def generate_device_id(self, pc_name: str) -> str:
        """Genera un ID único y consistente para el dispositivo"""
        try:
            if not pc_name or not pc_name.strip():
                return "UNKNOWN_ID"
                
            pc_name = pc_name.strip().upper()
            
            # Extraer la parte MX_XXXXX si existe (ej: "MX_PC001 Local" -> "MX_PC001")
            if pc_name.startswith("MX_"):
                # Tomar solo la parte MX_XXXXX (primer segmento)
                parts = pc_name.split(' ')
                if len(parts) > 0:
                    mx_part = parts[0].strip()
                    # Asegurar que tenga formato MX_XXXXX
                    if mx_part.startswith("MX_") and len(mx_part) > 3:
                        return mx_part
            
            # Para nombres sin MX_, usar hash MD5 de 12 caracteres
            hash_result = hashlib.md5(pc_name.encode()).hexdigest()[:12].upper()
            return f"HASH_{hash_result}"
            
        except Exception as e:
            logger.error(f"Error generando device_id: {e}")
            return "ERROR_ID"

    def get_or_create_device(self, device_data: Dict) -> tuple:
        """
        Obtiene o crea un dispositivo en la tabla devices.
        Retorna: (success, device_id, device_exists)
        """
        try:
            if not self.enabled: 
                return False, None, False
            
            pc_name = device_data.get('pc_name', '').strip()
            if not pc_name:
                logger.error("No se puede crear dispositivo sin pc_name")
                return False, None, False
            
            # Generar device_id consistente
            device_id = self.generate_device_id(pc_name)
            logger.info(f"🆔 Device ID generado para '{pc_name}': {device_id}")
            
            # Primero, intentar buscar el dispositivo por device_id
            logger.debug(f"🔍 Buscando dispositivo {device_id} en tabla devices...")
            
            search_result = self._make_appsheet_request(
                "devices", 
                "Find", 
                properties={"FilterQuery": f"[device_id] = '{device_id}'"}
            )
            
            device_exists = False
            
            # Verificar diferentes formatos de respuesta
            if search_result:
                if isinstance(search_result, list) and len(search_result) > 0:
                    device_exists = True
                    logger.debug(f"✅ Dispositivo encontrado en formato lista")
                elif isinstance(search_result, dict):
                    if 'Rows' in search_result and len(search_result['Rows']) > 0:
                        device_exists = True
                        logger.debug(f"✅ Dispositivo encontrado en formato Rows")
                    elif any(isinstance(v, list) and len(v) > 0 for v in search_result.values()):
                        device_exists = True
                        logger.debug(f"✅ Dispositivo encontrado en formato dict con lista")
            
            logger.info(f"📊 Dispositivo {device_id} existe en devices: {device_exists}")
            
            # Si no existe, crearlo
            if not device_exists:
                unit = device_data.get('unit', 'General')
                ip = device_data.get('public_ip', device_data.get('ip', ''))
                status = device_data.get('status', 'online')
                
                device_row = {
                    "device_id": device_id,
                    "pc_name": pc_name,
                    "unit": unit,
                    "public_ip": ip,
                    "status": status,
                    "updated_at": datetime.now(TZ_MX).isoformat()
                }
                
                logger.info(f"🔄 Creando dispositivo en tabla devices: {pc_name} (ID: {device_id})")
                
                create_result = self._make_appsheet_request("devices", "Add", [device_row])
                
                if create_result is not None:
                    logger.info(f"✅ Dispositivo {pc_name} creado exitosamente en tabla devices")
                    self.last_sync_time = datetime.now(TZ_MX)
                    return True, device_id, False
                else:
                    logger.error(f"❌ No se pudo crear dispositivo {pc_name} en tabla devices")
                    return False, device_id, False
            
            return True, device_id, True
                
        except Exception as e:
            logger.error(f"Error en get_or_create_device: {e}", exc_info=True)
            return False, None, False

    def add_history_entry(self, log_data: Dict) -> bool:
        """
        Guarda ficha en device_history.
        IMPORTANTE: Primero asegura que el dispositivo exista en devices.
        """
        try:
            if not self.enabled: 
                logger.warning("AppSheet deshabilitado, no se guardará ficha")
                return False
            
            logger.info(f"📝 Iniciando proceso para guardar ficha")
            
            # Obtener nombre del dispositivo
            device_name = log_data.get('device_name') or log_data.get('pc_name')
            if not device_name:
                logger.error("❌ Error: Falta nombre del dispositivo (device_name o pc_name)")
                return False

            logger.info(f"🔧 Procesando ficha para dispositivo: {device_name}")
            
            # 1. CRÍTICO: Asegurar que el dispositivo existe en la tabla devices
            # Esto es necesario porque device_id es una REFERENCIA
            logger.info(f"🔄 Verificando/creando dispositivo en tabla devices...")
            
            success, device_id, device_exists = self.get_or_create_device({
                "pc_name": device_name,
                "unit": log_data.get('unit', log_data.get('unit_snapshot', 'General')),
                "public_ip": log_data.get('public_ip', ''),
                "status": 'online'
            })
            
            if not success:
                logger.error("❌ No se pudo crear/verificar dispositivo en tabla devices. Abortando.")
                return False
            
            logger.info(f"✅ Dispositivo verificado en devices. ID: {device_id}, Ya existía: {device_exists}")
            
            # 2. Preparar datos para device_history
            timestamp = log_data.get('timestamp')
            if not timestamp:
                timestamp = datetime.now(TZ_MX).isoformat()
            
            # Componente válido (basado en lo que me dijiste)
            component = log_data.get('what', log_data.get('component', 'General'))
            valid_components = ['NUC', 'SD300', 'UPS', 'MODULO', 'COMPONENTES', 'TELTONIKA', 'General', 'Otro']
            if component not in valid_components:
                logger.warning(f"⚠️  Componente '{component}' no válido, usando 'General'")
                component = 'General'
            
            # Preparar fila para device_history
            history_row = {
                "device_id": device_id,  # REFERENCIA a devices.device_id
                "timestamp": timestamp,
                "requester": log_data.get('req', log_data.get('requester', 'Sistema')),
                "executor": log_data.get('exec', log_data.get('executor', 'Pendiente')),
                "action_type": log_data.get('action', log_data.get('action_type', 'Mantenimiento')),
                "component": component,
                "description": log_data.get('desc', log_data.get('description', '')),
                "is_resolved": log_data.get('solved', log_data.get('is_resolved', False)),
                "unit_snapshot": log_data.get('unit', log_data.get('unit_snapshot', 'General'))
            }
            
            # Formatear is_resolved para AppSheet (Yes/No)
            if isinstance(history_row["is_resolved"], bool):
                history_row["is_resolved"] = "TRUE" if history_row["is_resolved"] else "FALSE"
            elif isinstance(history_row["is_resolved"], str):
                resolved_lower = history_row["is_resolved"].lower()
                if resolved_lower in ['true', 'yes', 'si', 'verdadero', '1', 'verdad']:
                    history_row["is_resolved"] = "TRUE"
                else:
                    history_row["is_resolved"] = "FALSE"
            else:
                history_row["is_resolved"] = "FALSE"
            
            # Asegurar que todos los campos sean strings (AppSheet puede ser sensible)
            for key in history_row:
                if history_row[key] is None:
                    history_row[key] = ""
                elif not isinstance(history_row[key], str):
                    history_row[key] = str(history_row[key])
            
            logger.info(f"💾 Preparando para guardar en device_history...")
            logger.debug(f"📋 Datos a guardar: {json.dumps(history_row, indent=2, ensure_ascii=False)}")
            
            # 3. Guardar en device_history
            logger.info(f"📤 Enviando a device_history...")
            result = self._make_appsheet_request("device_history", "Add", [history_row])
            
            if result is not None:
                logger.info(f"✅ Ficha guardada exitosamente en device_history")
                logger.debug(f"📥 Respuesta AppSheet: {result}")
                
                # 4. Actualizar estado del dispositivo si es necesario
                action = str(log_data.get('action', '')).lower()
                if 'baja' in action or 'retiro' in action:
                    logger.info(f"📉 Marcando dispositivo {device_id} como 'offline' por baja")
                    self.update_device_status(device_id, 'offline')
                elif any(x in action for x in ['instalación', 'renovación', 'activación', 'alta', 'reactivación']):
                    logger.info(f"📈 Marcando dispositivo {device_id} como 'online' por instalación/renovación")
                    self.update_device_status(device_id, 'online')
                
                return True
            else:
                logger.error("❌ AppSheet rechazó la ficha en device_history")
                logger.error("⚠️  Posibles causas:")
                logger.error(f"   1. device_id '{device_id}' no existe en tabla devices o no es referencia válida")
                logger.error(f"   2. Error en formato de datos (columnas faltantes o incorrectas)")
                logger.error(f"   3. device_history necesita configuración especial (Primary Key, etc.)")
                logger.error(f"   4. Permisos insuficientes para escribir en device_history")
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
                
            logger.info(f"🔄 Actualizando estado de dispositivo {device_id} a '{status}'")
            
            # Primero buscar el dispositivo
            search_result = self._make_appsheet_request(
                "devices", 
                "Find", 
                properties={"FilterQuery": f"[device_id] = '{device_id}'"}
            )
            
            device_found = False
            if search_result:
                if isinstance(search_result, list) and len(search_result) > 0:
                    device_found = True
                elif isinstance(search_result, dict):
                    if 'Rows' in search_result and len(search_result['Rows']) > 0:
                        device_found = True
                    elif any(isinstance(v, list) and len(v) > 0 for v in search_result.values()):
                        device_found = True
            
            if device_found:
                update_row = {
                    "device_id": device_id,
                    "status": status,
                    "updated_at": datetime.now(TZ_MX).isoformat()
                }
                
                logger.debug(f"📋 Datos de actualización: {update_row}")
                result = self._make_appsheet_request("devices", "Edit", [update_row])
                
                if result is not None:
                    logger.info(f"✅ Estado de {device_id} actualizado a '{status}' en tabla devices")
                else:
                    logger.warning(f"⚠️  No se pudo actualizar estado de {device_id} en tabla devices")
            else:
                logger.warning(f"⚠️  Dispositivo {device_id} no encontrado en tabla devices para actualizar estado")
                
        except Exception as e:
            logger.error(f"Error en update_device_status: {e}")

    def get_full_history(self, limit: int = 200) -> List[Dict]:
        """Obtiene el historial completo de bitácora"""
        try:
            if not self.enabled: 
                logger.debug("AppSheet deshabilitado, retornando lista vacía")
                return []
            
            logger.info(f"📋 Solicitando historial completo (límite: {limit})...")
            
            result = self._make_appsheet_request(
                "device_history", 
                "Find", 
                properties={"Top": limit, "SortBy": "[timestamp] DESC"}
            )
            
            rows = []
            
            if isinstance(result, list):
                rows = result
                logger.info(f"✅ Historial obtenido (formato lista): {len(rows)} registros")
            elif isinstance(result, dict):
                if 'Rows' in result:
                    rows = result['Rows']
                    logger.info(f"✅ Historial obtenido (formato Rows): {len(rows)} registros")
                elif 'data' in result:
                    rows = result['data']
                    logger.info(f"✅ Historial obtenido (formato data): {len(rows)} registros")
                else:
                    # Buscar cualquier lista en el diccionario
                    for key, value in result.items():
                        if isinstance(value, list):
                            rows = value
                            logger.info(f"✅ Historial obtenido (clave '{key}'): {len(rows)} registros")
                            break
                    else:
                        # Si no encontramos lista, intentar extraer de estructura diferente
                        logger.warning(f"⚠️  Formato de respuesta inesperado: {type(result)}")
                        if result:
                            logger.debug(f"📋 Estructura recibida: {list(result.keys())}")
            
            # Ordenar por timestamp si no viene ordenado
            if rows:
                try:
                    rows.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                except Exception as e:
                    logger.warning(f"⚠️  No se pudo ordenar historial: {e}")
                
                # Log para debugging
                if len(rows) > 0:
                    sample = rows[0]
                    logger.debug(f"📊 Muestra registro: device_id={sample.get('device_id')}, acción={sample.get('action_type')}, fecha={sample.get('timestamp')}")
            
            return rows
                
        except Exception as e:
            logger.error(f"Error en get_full_history: {e}")
            return []

    def get_history_for_device(self, pc_name: str) -> List[Dict]:
        """Obtiene historial específico para un dispositivo"""
        try:
            if not self.enabled or not pc_name:
                return []
            
            # Generar device_id para buscar
            device_id = self.generate_device_id(pc_name)
            logger.info(f"🔍 Buscando historial para dispositivo: {pc_name}")
            logger.debug(f"🔍 Device ID calculado: {device_id}")
            
            # Obtener todo el historial
            all_history = self.get_full_history(limit=300)
            logger.debug(f"🔍 Historial total obtenido: {len(all_history)} registros")
            
            # Filtrar por device_id exacto
            exact_matches = []
            partial_matches = []
            
            for record in all_history:
                record_device_id = str(record.get('device_id', '')).upper().strip()
                search_device_id = device_id.upper().strip()
                
                # Coincidencia exacta
                if record_device_id == search_device_id:
                    exact_matches.append(record)
                # Coincidencia parcial (para debugging)
                elif search_device_id and record_device_id and search_device_id in record_device_id:
                    partial_matches.append(record)
                    logger.debug(f"🔍 Coincidencia parcial: {record_device_id} contiene {search_device_id}")
            
            logger.info(f"📊 Resultados búsqueda para {pc_name}:")
            logger.info(f"   Coincidencias exactas: {len(exact_matches)}")
            logger.info(f"   Coincidencias parciales: {len(partial_matches)}")
            
            # Devolver coincidencias exactas primero, luego parciales
            if exact_matches:
                return exact_matches
            elif partial_matches:
                logger.info(f"⚠️  Usando coincidencias parciales para {pc_name}")
                return partial_matches
            else:
                logger.info(f"📭 No se encontraron registros para {pc_name}")
                return []
            
        except Exception as e:
            logger.error(f"Error en get_history_for_device: {e}")
            return []

    def get_status_info(self) -> Dict[str, Any]:
        """Obtiene información del estado de conexión"""
        try:
            if not self.enabled:
                return {"status": "disabled", "available": False}
            
            # Probar conexión a ambas tablas
            logger.debug("🔍 Probando conexión a tabla devices...")
            devices_test = self._make_appsheet_request("devices", "Find", properties={"Top": 1})
            
            logger.debug("🔍 Probando conexión a tabla device_history...")
            history_test = self._make_appsheet_request("device_history", "Find", properties={"Top": 1})
            
            devices_ok = devices_test is not None
            history_ok = history_test is not None
            
            status_info = {
                "status": "enabled",
                "available": devices_ok and history_ok,
                "tables": {
                    "devices": "connected" if devices_ok else "disconnected",
                    "device_history": "connected" if history_ok else "disconnected"
                },
                "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
                "app_id": self.app_id[:8] + "..." if self.app_id else None
            }
            
            logger.info(f"📡 Estado AppSheet: {'✅ CONECTADO' if status_info['available'] else '❌ DESCONECTADO'}")
            logger.info(f"📊 Tablas: devices={status_info['tables']['devices']}, history={status_info['tables']['device_history']}")
            
            return status_info
            
        except Exception as e:
            logger.error(f"Error en get_status_info: {e}")
            return {"status": "error", "available": False}

    def get_system_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema"""
        try:
            if not self.enabled: 
                return {
                    'avg_latency': 0, 
                    'total_devices': 0, 
                    'total_history': 0,
                    'status': 'disabled'
                }
            
            stats = {
                'avg_latency': 0, 
                'total_devices': 0, 
                'total_history': 0,
                'status': 'connected',
                'last_sync': None
            }
            
            # Obtener conteo de dispositivos
            devices_result = self._make_appsheet_request("devices", "Find")
            if devices_result:
                if isinstance(devices_result, list):
                    stats['total_devices'] = len(devices_result)
                elif isinstance(devices_result, dict):
                    if 'Rows' in devices_result:
                        stats['total_devices'] = len(devices_result['Rows'])
                    elif 'data' in devices_result:
                        stats['total_devices'] = len(devices_result['data'])
            
            # Obtener conteo de historial
            history_result = self._make_appsheet_request("device_history", "Find", properties={"Top": 1000})
            if history_result:
                if isinstance(history_result, list):
                    stats['total_history'] = len(history_result)
                elif isinstance(history_result, dict):
                    if 'Rows' in history_result:
                        stats['total_history'] = len(history_result['Rows'])
                    elif 'data' in history_result:
                        stats['total_history'] = len(history_result['data'])
            
            if self.last_sync_time: 
                stats['last_sync'] = self.last_sync_time.isoformat()
            
            logger.debug(f"📊 Estadísticas: devices={stats['total_devices']}, history={stats['total_history']}")
                
            return stats
            
        except Exception as e:
            logger.error(f"Error en get_system_stats: {e}")
            return {
                'avg_latency': 0, 
                'total_devices': 0, 
                'total_history': 0,
                'status': 'error'
            }

    def test_history_connection(self) -> bool:
        """Prueba específica para la conexión con device_history"""
        try:
            if not self.enabled: 
                return False
            
            result = self._make_appsheet_request("device_history", "Find", properties={"Top": 1})
            return result is not None
                
        except Exception as e:
            logger.error(f"Error probando device_history: {e}")
            return False
