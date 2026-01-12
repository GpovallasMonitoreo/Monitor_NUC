import os
import requests
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class AppSheetService:
    """Servicio para interactuar con AppSheet Database - VERSIÓN CORREGIDA"""
    
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY', '')
        self.app_id = os.getenv('APPSHEET_APP_ID', '')
        self.base_url = os.getenv('APPSHEET_BASE_URL', 'https://api.appsheet.com/api/v2')
        
        # Verificar si está configurado
        if not self.api_key or not self.app_id or 'tu_api_key' in self.api_key:
            logger.warning("⚠️ AppSheet no configurado o usando placeholders")
            self.enabled = False
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService inicializado")
        
        # Test rápido de conexión
        self._test_initial_connection()
    
    def _test_initial_connection(self):
        """Test inicial de conexión a todas las tablas"""
        try:
            tables_to_test = ['devices', 'latency_history', 'alerts']
            for table in tables_to_test:
                if self._test_table_connection(table):
                    logger.info(f"✅ Tabla '{table}' accesible")
                else:
                    logger.warning(f"⚠️ Tabla '{table}' puede tener problemas")
        except Exception as e:
            logger.error(f"❌ Error en test inicial: {e}")
    
    def _test_table_connection(self, table_name: str) -> bool:
        """Testear conexión a una tabla específica"""
        try:
            payload = {
                "Action": "Get",
                "Properties": {
                    "Locale": "en-US",
                    "SelectColumns": [],
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
                # Intentar parsear respuesta
                try:
                    data = response.json()
                    return True
                except:
                    # Respuesta vacía pero status 200 (tabla vacía)
                    return True
            elif response.status_code == 404:
                logger.error(f"❌ Tabla '{table_name}' no existe en AppSheet")
                return False
            else:
                logger.warning(f"⚠️ Tabla '{table_name}' - Status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error testeando tabla '{table_name}': {e}")
            return False
    
    def generate_device_id(self, pc_name: str) -> str:
        """Generar ID único para dispositivo"""
        return hashlib.md5(pc_name.encode()).hexdigest()[:16].upper()
    
    def is_available(self) -> bool:
        """Verificar si AppSheet está disponible"""
        if not self.enabled:
            return False
            
        try:
            # Test simple con tabla devices
            return self._test_table_connection('devices')
        except Exception:
            return False
    
    def _make_safe_request(self, table: str, action: str, rows: List[Dict] = None) -> Optional[Any]:
        """Request segura que maneja respuestas no-JSON"""
        try:
            if not self.enabled:
                return None
            
            payload = {
                "Action": action,
                "Properties": {"Locale": "en-US"}
            }
            
            if rows and action in ["Add", "Edit", "Find"]:
                payload["Rows"] = rows
            
            logger.debug(f"AppSheet Request: {table}/{action}")
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            logger.debug(f"AppSheet Response Status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"AppSheet Error {table}/{action}: {response.status_code}")
                if response.text:
                    logger.error(f"Response text: {response.text[:200]}")
                return None
            
            # Manejar respuestas vacías
            if not response.text or response.text.strip() == '':
                logger.debug(f"AppSheet {table} - Respuesta vacía (probablemente éxito)")
                return {"success": True, "empty_response": True}
            
            # Intentar parsear JSON
            try:
                return response.json()
            except json.JSONDecodeError as e:
                logger.warning(f"AppSheet {table} - Respuesta no JSON: {response.text[:100]}")
                # Si no es JSON pero status es 200, probablemente fue exitoso
                return {"success": True, "non_json_response": response.text[:100]}
                
        except requests.exceptions.Timeout:
            logger.error(f"AppSheet {table} - Timeout")
            return None
        except Exception as e:
            logger.error(f"AppSheet {table} - Error: {e}")
            return None
    
    def upsert_device(self, device_data: Dict) -> bool:
        """Crear o actualizar dispositivo"""
        try:
            if not self.enabled:
                return False
                
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Formatear ubicación
            location = ""
            if device_data.get('lat') and device_data.get('lng'):
                location = f"{device_data['lat']},{device_data['lng']}"
            
            # Datos del dispositivo
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
            find_result = self._make_safe_request("devices", "Find", [{"device_id": device_id}])
            
            if find_result and isinstance(find_result, list) and len(find_result) > 0:
                # Actualizar existente
                device_row["_RowNumber"] = find_result[0].get("_RowNumber")
                action = "Edit"
                logger.debug(f"Actualizando dispositivo: {device_data['pc_name']}")
            else:
                # Crear nuevo
                device_row["created_at"] = datetime.now().isoformat()
                action = "Add"
                logger.debug(f"Creando dispositivo: {device_data['pc_name']}")
            
            result = self._make_safe_request("devices", action, [device_row])
            
            if result is not None:
                self.last_sync_time = datetime.now()
                logger.info(f"✅ Dispositivo {device_data['pc_name']} sincronizado")
                return True
            return False
                
        except Exception as e:
            logger.error(f"Error en upsert_device: {e}")
            return False
    
    def add_latency_record(self, device_data: Dict) -> bool:
        """Agregar registro de latencia - VERSIÓN SIMPLIFICADA Y SEGURA"""
        try:
            if not self.enabled:
                return False
                
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Obtener temperatura de forma segura
            def get_temp_safe(data):
                try:
                    # Primero temperatura directa
                    temp = data.get('temperature')
                    if temp is not None:
                        return float(temp)
                    
                    # Luego sensores extendidos
                    if data.get('extended_sensors') and 'Intel CPU' in data['extended_sensors']:
                        sensors = data['extended_sensors']['Intel CPU']
                        for sensor in sensors:
                            if sensor.get('tipo') == 'Temperature':
                                val = sensor.get('valor')
                                if val is not None:
                                    return float(val)
                except:
                    pass
                return 40.0
            
            # Crear registro de latencia - CAMPOS MÍNIMOS
            latency_row = {
                "device_id": device_id,
                "timestamp": datetime.now().isoformat(),
                "latency_ms": float(device_data.get('latency', 0)),
                "cpu_percent": float(device_data.get('cpu_load_percent', 0)),
                "ram_percent": float(device_data.get('ram_percent', 0)),
                "temperature_c": get_temp_safe(device_data),
                "disk_percent": float(device_data.get('disk_percent', 0)),
                "status": str(device_data.get('status', 'online')).lower()
            }
            
            logger.debug(f"Enviando registro de latencia para: {device_data['pc_name']}")
            
            result = self._make_safe_request("latency_history", "Add", [latency_row])
            
            if result is not None:
                logger.info(f"✅ Registro de latencia agregado para {device_data['pc_name']}")
                return True
            
            logger.error(f"❌ Falló registro de latencia para {device_data['pc_name']}")
            return False
                
        except Exception as e:
            logger.error(f"❌ Error crítico en add_latency_record: {e}")
            return False
    
    def add_alert(self, device_data: Dict, alert_type: str, message: str, severity: str = "medium") -> bool:
        """Agregar alerta - VERSIÓN ROBUSTA"""
        try:
            if not self.enabled:
                return False
                
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Crear alerta
            alert_row = {
                "device_id": device_id,
                "alert_type": str(alert_type)[:50],
                "severity": str(severity)[:20],
                "message": str(message)[:500],
                "timestamp": datetime.now().isoformat(),
                "resolved": False,
                "pc_name": str(device_data.get('pc_name', 'Unknown'))[:100]
            }
            
            result = self._make_safe_request("alerts", "Add", [alert_row])
            
            if result is not None:
                logger.info(f"✅ Alerta agregada: {device_data['pc_name']} - {message[:50]}...")
                return True
            return False
                
        except Exception as e:
            logger.error(f"Error en add_alert: {e}")
            return False
    
    def get_device_history(self, pc_name: str, limit: int = 50, days: int = 7) -> List[Dict]:
        """Obtener historial de un dispositivo"""
        try:
            if not self.enabled:
                return []
                
            device_id = self.generate_device_id(pc_name)
            
            result = self._make_safe_request("latency_history", "Get")
            
            if not result or not isinstance(result, list):
                return []
            
            # Filtrar por device_id
            filtered = [row for row in result if row.get('device_id') == device_id]
            
            # Filtrar por fecha si es posible
            try:
                cutoff_date = datetime.now() - timedelta(days=days)
                date_filtered = []
                for row in filtered:
                    timestamp = row.get('timestamp')
                    if timestamp:
                        try:
                            if 'T' in timestamp:
                                row_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            else:
                                row_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                            
                            if row_time >= cutoff_date:
                                date_filtered.append(row)
                        except:
                            date_filtered.append(row)
                filtered = date_filtered
            except:
                pass  # Si hay error en fechas, usar todos los registros
            
            # Ordenar y limitar
            filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"Error obteniendo historial para {pc_name}: {e}")
            return []
    
    def get_recent_alerts(self, limit: int = 20, unresolved_only: bool = True) -> List[Dict]:
        """Obtener alertas recientes"""
        try:
            if not self.enabled:
                return []
                
            result = self._make_safe_request("alerts", "Get")
            
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
            logger.error(f"Error obteniendo alertas: {e}")
            return []
    
    def get_system_stats(self, days: int = 1) -> Dict[str, Any]:
        """Obtener estadísticas - VERSIÓN TOLERANTE A FALLOS"""
        try:
            if not self.enabled:
                return self._get_default_stats()
            
            # Obtener datos con manejo de errores
            latency_data = self._make_safe_request("latency_history", "Get") or []
            devices_data = self._make_safe_request("devices", "Get") or []
            alerts_data = self._make_safe_request("alerts", "Get") or []
            
            # Asegurar que sean listas
            if not isinstance(latency_data, list):
                latency_data = []
            if not isinstance(devices_data, list):
                devices_data = []
            if not isinstance(alerts_data, list):
                alerts_data = []
            
            stats = self._get_default_stats()
            
            # Procesar solo si hay datos
            if latency_data:
                # Calcular promedios básicos
                latencies = []
                cpus = []
                online_count = 0
                
                for row in latency_data:
                    try:
                        # Latencia
                        lat = row.get('latency_ms')
                        if lat is not None:
                            latencies.append(float(lat))
                        
                        # CPU
                        cpu = row.get('cpu_percent')
                        if cpu is not None:
                            cpus.append(float(cpu))
                        
                        # Estado
                        if row.get('status') == 'online':
                            online_count += 1
                    except:
                        continue
                
                if latencies:
                    stats['avg_latency'] = sum(latencies) / len(latencies)
                if cpus:
                    stats['avg_cpu'] = sum(cpus) / len(cpus)
                
                stats['total_records'] = len(latency_data)
                stats['uptime_percent'] = (online_count / len(latency_data) * 100) if latency_data else 0
            
            # Contar dispositivos y alertas
            stats['total_devices'] = len(devices_data)
            
            active_alerts = len([a for a in alerts_data if not a.get('resolved', True)])
            stats['active_alerts'] = active_alerts
            
            # Última sincronización
            if self.last_sync_time:
                stats['last_sync'] = self.last_sync_time.isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculando estadísticas: {e}")
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
            'note': 'Datos desde AppSheet'
        }
    
    def get_last_sync_time(self) -> Optional[datetime]:
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
            
            # 2. Agregar registro de latencia (SIEMPRE intentar)
            results['latency_synced'] = self.add_latency_record(device_data)
            
            # 3. Generar alertas solo si es crítico
            cpu = device_data.get('cpu_load_percent', 0)
            status = device_data.get('status', 'online')
            
            if cpu > 90 or status in ['critical', 'offline']:
                alert_type = 'high_cpu' if cpu > 90 else status
                message = f"CPU: {cpu}%" if cpu > 90 else f"Estado: {status}"
                severity = 'high' if cpu > 90 else 'medium'
                
                results['alert_generated'] = self.add_alert(
                    device_data, alert_type, message, severity
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error en sync_device_complete: {e}")
            return results
    
    def get_status_info(self) -> Dict[str, Any]:
        """Información de estado detallada"""
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "AppSheet no configurado",
                "available": False,
                "last_sync": None
            }
        
        is_available = self.is_available()
        
        # Test adicional de tablas
        tables_status = {}
        for table in ['devices', 'latency_history', 'alerts']:
            tables_status[table] = self._test_table_connection(table)
        
        return {
            "status": "enabled",
            "available": is_available,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "message": "AppSheet disponible" if is_available else "AppSheet no responde",
            "tables_status": tables_status,
            "has_api_key": bool(self.api_key and 'tu_api_key' not in self.api_key),
            "has_app_id": bool(self.app_id)
        }
