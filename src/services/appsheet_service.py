import os
import requests
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class AppSheetService:
    """Servicio para interactuar con AppSheet Database - VERSIÓN DEPURADA"""
    
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY', '')
        self.app_id = os.getenv('APPSHEET_APP_ID', '')
        self.base_url = os.getenv('APPSHEET_BASE_URL', 'https://api.appsheet.com/api/v2')
        
        # Verificar si está configurado
        if not self.api_key or not self.app_id or self.api_key == 'tu_api_key_de_appsheet_aqui':
            logger.warning("⚠️ AppSheet no configurado correctamente")
            self.enabled = False
            self.config_status = "not_configured"
            return
            
        self.enabled = True
        self.config_status = "configured"
        
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService inicializado - App ID: {self.app_id[:8]}...")
        
        # Verificar conexión inmediatamente
        self._test_connection()
    
    def _test_connection(self):
        """Verificar conexión a AppSheet al iniciar"""
        try:
            if self.is_available():
                logger.info("✅ Conexión AppSheet verificada exitosamente")
                self.config_status = "connected"
            else:
                logger.warning("⚠️ AppSheet configurado pero no disponible")
                self.config_status = "configured_but_unavailable"
        except Exception as e:
            logger.error(f"❌ Error verificando conexión AppSheet: {e}")
            self.config_status = "error"
    
    def generate_device_id(self, pc_name: str) -> str:
        """Generar ID único para dispositivo - COMPATIBLE CON APPSHEET"""
        # Hash MD5 y tomar primeros 16 caracteres en mayúsculas
        return hashlib.md5(pc_name.encode()).hexdigest()[:16].upper()
    
    def is_available(self) -> bool:
        """Verificar si AppSheet está disponible"""
        if not self.enabled:
            return False
            
        try:
            # Método más simple para verificar conexión
            payload = {
                "Action": "Get",
                "Properties": {
                    "Locale": "en-US",
                    "SelectColumns": ["device_id"],
                    "Top": 1
                }
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/devices/Action",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            # Verificar respuesta válida
            if response.status_code == 200:
                # Intentar parsear JSON
                try:
                    data = response.json()
                    return isinstance(data, list)
                except:
                    return True  # Aunque no sea JSON válido, la conexión funciona
            return False
            
        except requests.exceptions.Timeout:
            logger.warning("⚠️ Timeout verificando AppSheet")
            return False
        except requests.exceptions.ConnectionError:
            logger.warning("⚠️ Error de conexión a AppSheet")
            return False
        except Exception as e:
            logger.error(f"❌ Error inesperado en is_available: {e}")
            return False
    
    def _make_request(self, table: str, action: str, rows: List[Dict] = None, 
                     select_columns: List[str] = None, top: int = None) -> Optional[Any]:
        """Método genérico para hacer requests a AppSheet"""
        try:
            if not self.enabled:
                return None
            
            payload = {
                "Action": action,
                "Properties": {
                    "Locale": "en-US"
                }
            }
            
            # Agregar propiedades opcionales
            if select_columns:
                payload["Properties"]["SelectColumns"] = select_columns
            if top:
                payload["Properties"]["Top"] = top
            if rows and action in ["Add", "Edit", "Find"]:
                payload["Rows"] = rows
            
            logger.debug(f"Enviando request a AppSheet - Tabla: {table}, Acción: {action}")
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            logger.debug(f"Respuesta AppSheet - Status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"❌ Error AppSheet {table}/{action}: {response.status_code} - {response.text[:200]}")
                return None
            
            # Intentar parsear JSON
            try:
                return response.json()
            except json.JSONDecodeError:
                logger.warning(f"⚠️ Respuesta no JSON de AppSheet: {response.text[:100]}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout en AppSheet {table}/{action}")
            return None
        except Exception as e:
            logger.error(f"❌ Error en _make_request: {e}")
            return None
    
    def upsert_device(self, device_data: Dict) -> bool:
        """Crear o actualizar dispositivo en AppSheet"""
        try:
            if not self.enabled:
                return False
                
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Formatear ubicación
            location = ""
            if device_data.get('lat') and device_data.get('lng'):
                location = f"{device_data['lat']},{device_data['lng']}"
            
            # Datos del dispositivo según tu estructura
            device_row = {
                "device_id": device_id,
                "pc_name": device_data['pc_name'],
                "unit": device_data.get('unit', 'General'),
                "public_ip": device_data.get('public_ip', device_data.get('ip', '')),
                "last_known_location": location,
                "is_active": device_data.get('status', 'online') != 'offline',
                "updated_at": datetime.now().isoformat()
            }
            
            # Buscar si existe
            existing = self._find_device(device_id)
            
            if existing:
                # Actualizar existente
                device_row["_RowNumber"] = existing["_RowNumber"]
                action = "Edit"
                logger.debug(f"Actualizando dispositivo existente: {device_data['pc_name']}")
            else:
                # Crear nuevo
                device_row["created_at"] = datetime.now().isoformat()
                action = "Add"
                logger.debug(f"Creando nuevo dispositivo: {device_data['pc_name']}")
            
            result = self._make_request("devices", action, [device_row])
            
            if result is not None:
                logger.info(f"✅ Dispositivo {device_data['pc_name']} sincronizado con AppSheet")
                self.last_sync_time = datetime.now()
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en upsert_device para {device_data.get('pc_name', 'unknown')}: {e}")
            return False
    
    def _find_device(self, device_id: str) -> Optional[Dict]:
        """Buscar dispositivo por ID"""
        try:
            result = self._make_request(
                "devices", 
                "Find", 
                [{"device_id": device_id}]
            )
            
            if result and isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
            
        except Exception as e:
            logger.error(f"Error buscando dispositivo {device_id}: {e}")
            return None
    
    def add_latency_record(self, device_data: Dict) -> bool:
        """Agregar registro de latencia - VERSIÓN SIMPLIFICADA"""
        try:
            if not self.enabled:
                return False
                
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Función simplificada para temperatura
            def get_temp(data):
                # Primero intentar temperatura directa
                if data.get('temperature'):
                    return data['temperature']
                # Luego sensores extendidos
                if data.get('extended_sensors') and 'Intel CPU' in data['extended_sensors']:
                    sensors = data['extended_sensors']['Intel CPU']
                    temp_sensor = next((s for s in sensors if s.get('tipo') == 'Temperature'), None)
                    return temp_sensor.get('valor', 40) if temp_sensor else 40
                return 40
            
            # Datos de latencia - SOLO CAMPOS NECESARIOS
            latency_row = {
                "device_id": device_id,
                "timestamp": datetime.now().isoformat(),
                "latency_ms": float(device_data.get('latency', 0)),
                "cpu_percent": float(device_data.get('cpu_load_percent', 0)),
                "ram_percent": float(device_data.get('ram_percent', 0)),
                "temperature_c": float(get_temp(device_data)),
                "disk_percent": float(device_data.get('disk_percent', 0)),
                "status": device_data.get('status', 'online')
            }
            
            # NOTA: Removí extended_sensors temporalmente para evitar errores
            # Si necesitas este campo, asegúrate de que sea string JSON válido
            
            result = self._make_request("latency_history", "Add", [latency_row])
            
            if result is not None:
                logger.debug(f"✅ Registro de latencia para {device_data['pc_name']}")
                return True
            else:
                logger.error(f"❌ Falló registro de latencia para {device_data['pc_name']}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en add_latency_record: {e}")
            return False
    
    def add_alert(self, device_data: Dict, alert_type: str, message: str, severity: str = "medium") -> bool:
        """Agregar alerta - VERSIÓN SIMPLIFICADA"""
        try:
            if not self.enabled:
                return False
                
            device_id = self.generate_device_id(device_data['pc_name'])
            
            alert_row = {
                "device_id": device_id,
                "alert_type": alert_type,
                "severity": severity,
                "message": message[:500],  # Limitar longitud
                "timestamp": datetime.now().isoformat(),
                "resolved": False,
                "pc_name": device_data['pc_name'][:100]  # Campo adicional
            }
            
            result = self._make_request("alerts", "Add", [alert_row])
            
            if result is not None:
                logger.info(f"✅ Alerta para {device_data['pc_name']}: {message[:50]}...")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en add_alert: {e}")
            return False
    
    def get_device_history(self, pc_name: str, limit: int = 50, days: int = 7) -> List[Dict]:
        """Obtener historial de un dispositivo"""
        try:
            if not self.enabled:
                return []
                
            device_id = self.generate_device_id(pc_name)
            
            result = self._make_request(
                "latency_history",
                "Get",
                select_columns=[
                    "record_id", "device_id", "timestamp", 
                    "latency_ms", "cpu_percent", "ram_percent", 
                    "temperature_c", "disk_percent", "status"
                ]
            )
            
            if not result or not isinstance(result, list):
                return []
            
            # Filtrar por device_id y fecha
            cutoff_date = datetime.now() - timedelta(days=days)
            filtered = []
            
            for row in result:
                if row.get('device_id') == device_id:
                    try:
                        # Intentar parsear fecha
                        timestamp = row.get('timestamp', '')
                        if timestamp:
                            # Manejar diferentes formatos de fecha
                            if 'T' in timestamp:
                                row_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            else:
                                row_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                            
                            if row_time >= cutoff_date:
                                filtered.append(row)
                    except (ValueError, TypeError):
                        # Si hay error, incluir de todos modos
                        filtered.append(row)
            
            # Ordenar y limitar
            filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo historial para {pc_name}: {e}")
            return []
    
    def get_recent_alerts(self, limit: int = 20, unresolved_only: bool = True) -> List[Dict]:
        """Obtener alertas recientes"""
        try:
            if not self.enabled:
                return []
                
            result = self._make_request(
                "alerts",
                "Get",
                select_columns=[
                    "alert_id", "device_id", "pc_name", "alert_type",
                    "severity", "message", "timestamp", "resolved"
                ]
            )
            
            if not result or not isinstance(result, list):
                return []
            
            # Filtrar
            filtered = []
            for alert in result:
                if unresolved_only and alert.get('resolved'):
                    continue
                filtered.append(alert)
            
            # Ordenar
            filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo alertas: {e}")
            return []
    
    def get_system_stats(self, days: int = 1) -> Dict[str, Any]:
        """Obtener estadísticas del sistema - VERSIÓN ROBUSTA"""
        try:
            if not self.enabled:
                return self._get_default_stats()
            
            # Obtener datos de latencia_history
            latency_data = self._make_request(
                "latency_history",
                "Get",
                select_columns=[
                    "latency_ms", "cpu_percent", "ram_percent", 
                    "temperature_c", "status", "timestamp"
                ]
            )
            
            # Obtener datos de devices
            devices_data = self._make_request(
                "devices",
                "Get",
                select_columns=["device_id"]
            )
            
            # Obtener alertas
            alerts_data = self._make_request(
                "alerts",
                "Get",
                select_columns=["alert_id", "resolved"]
            )
            
            # Inicializar estadísticas
            stats = self._get_default_stats()
            
            # Procesar datos de latencia si están disponibles
            if latency_data and isinstance(latency_data, list):
                cutoff_date = datetime.now() - timedelta(days=days)
                recent_data = []
                
                for row in latency_data:
                    try:
                        timestamp = row.get('timestamp', '')
                        if timestamp:
                            # Parsear fecha
                            if 'T' in timestamp:
                                row_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            else:
                                row_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                            
                            if row_time >= cutoff_date:
                                recent_data.append(row)
                    except:
                        continue
                
                if recent_data:
                    # Calcular promedios
                    latencies = []
                    cpus = []
                    
                    for row in recent_data:
                        latency = row.get('latency_ms')
                        cpu = row.get('cpu_percent')
                        
                        if latency is not None:
                            try:
                                latencies.append(float(latency))
                            except:
                                pass
                        
                        if cpu is not None:
                            try:
                                cpus.append(float(cpu))
                            except:
                                pass
                    
                    # Calcular uptime
                    total = len(recent_data)
                    online = len([r for r in recent_data if r.get('status') == 'online'])
                    uptime = (online / total * 100) if total > 0 else 100
                    
                    stats.update({
                        'avg_latency': sum(latencies) / len(latencies) if latencies else 0,
                        'avg_cpu': sum(cpus) / len(cpus) if cpus else 0,
                        'total_records': len(recent_data),
                        'uptime_percent': round(uptime, 1)
                    })
            
            # Contar dispositivos
            if devices_data and isinstance(devices_data, list):
                stats['total_devices'] = len(devices_data)
            
            # Contar alertas activas
            if alerts_data and isinstance(alerts_data, list):
                active_alerts = len([a for a in alerts_data if not a.get('resolved', True)])
                stats['active_alerts'] = active_alerts
            
            # Agregar última sincronización
            if self.last_sync_time:
                stats['last_sync'] = self.last_sync_time.isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error calculando estadísticas: {e}")
            return self._get_default_stats()
    
    def _get_default_stats(self) -> Dict[str, Any]:
        """Estadísticas por defecto"""
        return {
            'avg_latency': 0,
            'avg_cpu': 0,
            'total_records': 0,
            'total_devices': 0,
            'uptime_percent': 0,
            'active_alerts': 0,
            'last_sync': None,
            'note': 'Estadísticas por defecto'
        }
    
    def get_last_sync_time(self) -> Optional[datetime]:
        """Obtener última hora de sincronización"""
        return self.last_sync_time
    
    def sync_device_complete(self, device_data: Dict) -> Dict[str, bool]:
        """Sincronización completa de un dispositivo"""
        results = {
            'device_synced': False,
            'latency_synced': False,
            'alert_generated': False
        }
        
        if not self.enabled:
            return results
        
        try:
            # 1. Sincronizar dispositivo
            results['device_synced'] = self.upsert_device(device_data)
            
            # 2. Agregar registro de latencia
            results['latency_synced'] = self.add_latency_record(device_data)
            
            # 3. Verificar alertas (sólo si hay datos críticos)
            if (device_data.get('cpu_load_percent', 0) > 90 or 
                device_data.get('status') in ['critical', 'offline']):
                
                alert_type = "high_cpu" if device_data.get('cpu_load_percent', 0) > 90 else device_data.get('status')
                alert_msg = f"CPU: {device_data.get('cpu_load_percent', 0)}%" if alert_type == "high_cpu" else f"Estado: {device_data.get('status')}"
                
                results['alert_generated'] = self.add_alert(
                    device_data, 
                    alert_type, 
                    alert_msg, 
                    'high' if device_data.get('cpu_load_percent', 0) > 90 else 'medium'
                )
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error en sync_device_complete: {e}")
            return results
    
    def get_status_info(self) -> Dict[str, Any]:
        """Obtener información completa del estado de AppSheet"""
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "AppSheet no está configurado",
                "available": False,
                "config_status": self.config_status,
                "last_sync": None
            }
        
        is_available = self.is_available()
        
        return {
            "status": "enabled",
            "available": is_available,
            "config_status": self.config_status,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "message": "AppSheet disponible" if is_available else "AppSheet no responde",
            "api_key_configured": bool(self.api_key and self.api_key != 'tu_api_key_de_appsheet_aqui'),
            "app_id_configured": bool(self.app_id),
            "base_url": self.base_url
        }
