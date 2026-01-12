import os
import requests
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class AppSheetService:
    """Servicio para interactuar con AppSheet Database - ESTRUCTURA ESPECÍFICA"""
    
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY')
        self.app_id = os.getenv('APPSHEET_APP_ID')
        self.base_url = os.getenv('APPSHEET_BASE_URL', 'https://api.appsheet.com/api/v2')
        
        if not self.api_key or not self.app_id:
            logger.warning("⚠️ AppSheet no configurado: APPSHEET_API_KEY y APPSHEET_APP_ID son requeridos")
            self.enabled = False
            return
            
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        
        self.last_sync_time = None
        self.enabled = True
        logger.info(f"✅ AppSheetService inicializado para App ID: {self.app_id[:8]}...")
    
    def generate_device_id(self, pc_name: str) -> str:
        """Generar ID único para dispositivo basado en nombre - MÉTODO ACTUALIZADO"""
        # Usar hash más corto para AppSheet
        return hashlib.md5(pc_name.encode()).hexdigest()[:16].upper()
    
    def is_available(self) -> bool:
        """Verificar si AppSheet está disponible y configurado"""
        if not self.enabled:
            return False
            
        try:
            # Intentar obtener un solo registro de devices para verificar conexión
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
            
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"⚠️ AppSheet no disponible: {e}")
            return False
    
    def upsert_device(self, device_data: Dict) -> bool:
        """Crear o actualizar dispositivo en AppSheet - ADAPTADO A TU ESTRUCTURA"""
        try:
            if not self.enabled:
                return False
                
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Formatear ubicación según tu estructura
            location = ""
            if device_data.get('lat') and device_data.get('lng'):
                location = f"{device_data['lat']},{device_data['lng']}"
            elif device_data.get('location'):
                location = device_data.get('location')
            
            # Preparar datos según TU estructura de tabla 'devices'
            device_row = {
                "device_id": device_id,
                "pc_name": device_data['pc_name'],
                "unit": device_data.get('unit', 'General'),
                "public_ip": device_data.get('public_ip', device_data.get('ip', '')),
                "last_known_location": location,
                "is_active": device_data.get('status', 'online') != 'offline',
                "updated_at": datetime.now().isoformat()
            }
            
            # Buscar dispositivo existente
            existing = self._find_device(device_id)
            
            if existing:
                # Actualizar dispositivo existente
                device_row["_RowNumber"] = existing["_RowNumber"]
                action = "Edit"
            else:
                # Crear nuevo dispositivo
                device_row["created_at"] = datetime.now().isoformat()
                action = "Add"
            
            payload = {
                "Action": action,
                "Properties": {
                    "Locale": "en-US"
                },
                "Rows": [device_row]
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/devices/Action",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Dispositivo {device_data['pc_name']} sincronizado con AppSheet")
                self.last_sync_time = datetime.now()
                return True
            else:
                logger.error(f"❌ Error sincronizando dispositivo: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en upsert_device: {e}")
            return False
    
    def _find_device(self, device_id: str) -> Optional[Dict]:
        """Buscar dispositivo por ID (interno)"""
        try:
            payload = {
                "Action": "Find",
                "Properties": {
                    "Locale": "en-US"
                },
                "Rows": [{
                    "device_id": device_id
                }]
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/devices/Action",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            data = response.json()
            return data[0] if data and len(data) > 0 else None
            
        except Exception as e:
            logger.error(f"Error buscando dispositivo {device_id}: {e}")
            return None
    
    def add_latency_record(self, device_data: Dict) -> bool:
        """Agregar registro de latencia al historial - ADAPTADO A TU ESTRUCTURA"""
        try:
            if not self.enabled:
                return False
                
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Función para obtener temperatura (manteniendo tu lógica)
            def get_temp(data):
                if data.get('extended_sensors') and 'Intel CPU' in data['extended_sensors']:
                    temp_sensor = next((s for s in data['extended_sensors']['Intel CPU'] 
                                      if s.get('tipo') == 'Temperature'), None)
                    return temp_sensor.get('valor', 40) if temp_sensor else 40
                return data.get('temperature', 40)
            
            # Preparar registro según TU estructura de tabla 'latency_history'
            latency_row = {
                "device_id": device_id,
                "timestamp": datetime.now().isoformat(),
                "latency_ms": device_data.get('latency', 0),
                "cpu_percent": device_data.get('cpu_load_percent', 0),
                "ram_percent": device_data.get('ram_percent', 0),
                "temperature_c": get_temp(device_data),
                "disk_percent": device_data.get('disk_percent', 0),
                "status": device_data.get('status', 'online'),
                "extended_sensors": json.dumps(device_data.get('extended_sensors', {}), ensure_ascii=False)
            }
            
            payload = {
                "Action": "Add",
                "Properties": {
                    "Locale": "en-US"
                },
                "Rows": [latency_row]
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/latency_history/Action",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                logger.debug(f"✅ Registro de latencia agregado para {device_data['pc_name']}")
                return True
            else:
                logger.error(f"❌ Error agregando registro de latencia: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en add_latency_record: {e}")
            return False
    
    def add_alert(self, device_data: Dict, alert_type: str, message: str, severity: str = "medium") -> bool:
        """Agregar alerta al sistema - ADAPTADO A TU ESTRUCTURA"""
        try:
            if not self.enabled:
                return False
                
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Preparar alerta según TU estructura de tabla 'alerts'
            alert_row = {
                "device_id": device_id,
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "resolved": False,
                "pc_name": device_data['pc_name']  # Campo adicional para referencia rápida
            }
            
            payload = {
                "Action": "Add",
                "Properties": {
                    "Locale": "en-US"
                },
                "Rows": [alert_row]
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/alerts/Action",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Alerta agregada para {device_data['pc_name']}: {message}")
                return True
            else:
                logger.error(f"❌ Error agregando alerta: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en add_alert: {e}")
            return False
    
    def get_device_history(self, pc_name: str, limit: int = 50, days: int = 7) -> List[Dict]:
        """Obtener historial de un dispositivo - OPTIMIZADO"""
        try:
            if not self.enabled:
                return []
                
            device_id = self.generate_device_id(pc_name)
            
            # Obtener todos los registros (AppSheet no tiene paginación nativa en la API)
            payload = {
                "Action": "Get",
                "Properties": {
                    "Locale": "en-US",
                    "SelectColumns": [
                        "record_id", "device_id", "timestamp", 
                        "latency_ms", "cpu_percent", "ram_percent", 
                        "temperature_c", "disk_percent", "status"
                    ]
                }
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/latency_history/Action",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code != 200:
                return []
                
            all_data = response.json()
            
            # Filtrar por device_id y fecha
            cutoff_date = datetime.now() - timedelta(days=days)
            filtered = []
            
            for row in all_data:
                if row.get('device_id') == device_id:
                    try:
                        row_time = datetime.fromisoformat(row.get('timestamp', '').replace('Z', '+00:00'))
                        if row_time >= cutoff_date:
                            filtered.append(row)
                    except (ValueError, TypeError):
                        # Si hay error en el formato, incluir de todos modos
                        filtered.append(row)
            
            # Ordenar por timestamp descendente y limitar
            filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo historial para {pc_name}: {e}")
            return []
    
    def get_recent_alerts(self, limit: int = 20, unresolved_only: bool = True) -> List[Dict]:
        """Obtener alertas recientes - OPTIMIZADO"""
        try:
            if not self.enabled:
                return []
                
            payload = {
                "Action": "Get",
                "Properties": {
                    "Locale": "en-US",
                    "SelectColumns": [
                        "alert_id", "device_id", "pc_name", "alert_type",
                        "severity", "message", "timestamp", "resolved"
                    ]
                }
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/alerts/Action",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code != 200:
                return []
                
            all_alerts = response.json()
            
            # Filtrar
            filtered = []
            for alert in all_alerts:
                if unresolved_only and alert.get('resolved'):
                    continue
                filtered.append(alert)
            
            # Ordenar por timestamp descendente
            filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo alertas: {e}")
            return []
    
    def get_system_stats(self, days: int = 1) -> Dict[str, Any]:
        """Obtener estadísticas del sistema - OPTIMIZADO"""
        try:
            if not self.enabled:
                return self._get_default_stats()
                
            # Obtener historial reciente
            payload = {
                "Action": "Get",
                "Properties": {
                    "Locale": "en-US",
                    "SelectColumns": [
                        "latency_ms", "cpu_percent", "ram_percent", 
                        "temperature_c", "status", "timestamp"
                    ]
                }
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/latency_history/Action",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code != 200:
                return self._get_default_stats()
                
            all_data = response.json()
            
            # Filtrar por fecha
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_data = []
            
            for row in all_data:
                try:
                    row_time = datetime.fromisoformat(row.get('timestamp', '').replace('Z', '+00:00'))
                    if row_time >= cutoff_date:
                        recent_data.append(row)
                except (ValueError, TypeError):
                    continue
            
            if not recent_data:
                return self._get_default_stats()
            
            # Calcular promedios
            latencies = [float(r.get('latency_ms', 0)) for r in recent_data if r.get('latency_ms') is not None]
            cpus = [float(r.get('cpu_percent', 0)) for r in recent_data if r.get('cpu_percent') is not None]
            
            # Calcular uptime
            total = len(recent_data)
            online = len([r for r in recent_data if r.get('status') == 'online'])
            uptime = (online / total * 100) if total > 0 else 100
            
            # Obtener alertas activas
            active_alerts = len(self.get_recent_alerts(limit=100, unresolved_only=True))
            
            # Obtener total de dispositivos únicos
            devices_response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/devices/Action",
                headers=self.headers,
                json={
                    "Action": "Get",
                    "Properties": {
                        "Locale": "en-US",
                        "SelectColumns": ["device_id"]
                    }
                },
                timeout=10
            )
            
            total_devices = 0
            if devices_response.status_code == 200:
                total_devices = len(devices_response.json())
            
            return {
                'avg_latency': sum(latencies) / len(latencies) if latencies else 0,
                'avg_cpu': sum(cpus) / len(cpus) if cpus else 0,
                'total_records': len(recent_data),
                'total_devices': total_devices,
                'uptime_percent': round(uptime, 1),
                'active_alerts': active_alerts,
                'last_sync': self.last_sync_time.isoformat() if self.last_sync_time else None
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculando estadísticas: {e}")
            return self._get_default_stats()
    
    def _get_default_stats(self) -> Dict[str, Any]:
        """Estadísticas por defecto cuando AppSheet no está disponible"""
        return {
            'avg_latency': 0,
            'avg_cpu': 0,
            'total_records': 0,
            'total_devices': 0,
            'uptime_percent': 0,
            'active_alerts': 0,
            'last_sync': None
        }
    
    def get_last_sync_time(self) -> Optional[datetime]:
        """Obtener última hora de sincronización"""
        return self.last_sync_time
    
    def sync_device_complete(self, device_data: Dict) -> Dict[str, bool]:
        """Sincronización completa de un dispositivo (dispositivo + historial + alertas)"""
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
            
            # 3. Verificar y generar alertas si es necesario
            alert_generated = False
            
            # Verificar CPU alta
            if device_data.get('cpu_load_percent', 0) > 90:
                alert_msg = f"CPU al {device_data.get('cpu_load_percent', 0)}%"
                if self.add_alert(device_data, 'high_cpu', alert_msg, 'high'):
                    alert_generated = True
            
            # Verificar temperatura alta
            temp = device_data.get('temperature', 0)
            if temp > 70:
                alert_msg = f"Temperatura: {temp}°C"
                if self.add_alert(device_data, 'high_temp', alert_msg, 'medium'):
                    alert_generated = True
            
            # Verificar estado crítico/offline
            if device_data.get('status') == 'critical':
                alert_msg = "Estado crítico detectado"
                if self.add_alert(device_data, 'critical_status', alert_msg, 'critical'):
                    alert_generated = True
            elif device_data.get('status') == 'offline':
                alert_msg = "Dispositivo offline"
                if self.add_alert(device_data, 'offline', alert_msg, 'high'):
                    alert_generated = True
            
            results['alert_generated'] = alert_generated
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error en sync_device_complete: {e}")
            return results
    
    def get_all_devices(self) -> List[Dict]:
        """Obtener todos los dispositivos registrados en AppSheet"""
        try:
            if not self.enabled:
                return []
                
            payload = {
                "Action": "Get",
                "Properties": {
                    "Locale": "en-US",
                    "SelectColumns": [
                        "device_id", "pc_name", "unit", "public_ip",
                        "last_known_location", "is_active", "created_at", "updated_at"
                    ]
                }
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/devices/Action",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return []
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo dispositivos: {e}")
            return []
