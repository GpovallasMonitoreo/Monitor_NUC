import os
import requests
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class AppSheetService:
    """Servicio para interactuar con AppSheet Database"""
    
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY')
        self.app_id = os.getenv('APPSHEET_APP_ID')
        self.base_url = os.getenv('APPSHEET_BASE_URL', 'https://api.appsheet.com/api/v2')
        
        if not self.api_key or not self.app_id:
            raise ValueError("APPSHEET_API_KEY y APPSHEET_APP_ID son requeridos")
        
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        
        self.last_sync_time = None
        logger.info(f"AppSheetService inicializado para App ID: {self.app_id[:8]}...")
    
    def generate_device_id(self, pc_name: str) -> str:
        """Generar ID único para dispositivo basado en nombre"""
        return hashlib.md5(pc_name.encode()).hexdigest()[:12]
    
    def is_available(self) -> bool:
        """Verificar si AppSheet está disponible"""
        try:
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
            logger.warning(f"AppSheet no disponible: {e}")
            return False
    
    def upsert_device(self, device_data: Dict) -> bool:
        """Crear o actualizar dispositivo en AppSheet"""
        try:
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Obtener ubicación si existe
            location = ""
            if device_data.get('lat') and device_data.get('lng'):
                location = f"{device_data['lat']},{device_data['lng']}"
            
            payload = {
                "Action": "Add",
                "Properties": {
                    "Locale": "en-US"
                },
                "Rows": [{
                    "device_id": device_id,
                    "pc_name": device_data['pc_name'],
                    "unit": device_data.get('unit', 'General'),
                    "public_ip": device_data.get('public_ip', device_data.get('ip', '')),
                    "last_known_location": location,
                    "is_active": device_data.get('status', 'online') != 'offline',
                    "last_seen": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }]
            }
            
            # Buscar dispositivo existente
            existing = self._find_device(device_id)
            if existing:
                payload["Action"] = "Edit"
                payload["Rows"][0]["_RowNumber"] = existing["_RowNumber"]
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/devices/Action",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(f"Dispositivo {device_data['pc_name']} sincronizado con AppSheet")
                self.last_sync_time = datetime.now()
                return True
            else:
                logger.error(f"Error sincronizando dispositivo: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error en upsert_device: {e}")
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
                json=payload
            )
            
            data = response.json()
            return data[0] if data else None
            
        except Exception:
            return None
    
    def add_latency_record(self, device_data: Dict) -> bool:
        """Agregar registro de latencia al historial"""
        try:
            device_id = self.generate_device_id(device_data['pc_name'])
            
            # Función para temperatura
            def get_temp(data):
                if data.get('extended_sensors') and 'Intel CPU' in data['extended_sensors']:
                    temp_sensor = next((s for s in data['extended_sensors']['Intel CPU'] 
                                      if s.get('tipo') == 'Temperature'), None)
                    return temp_sensor.get('valor', 40) if temp_sensor else 40
                return data.get('temperature', 40)
            
            payload = {
                "Action": "Add",
                "Properties": {
                    "Locale": "en-US"
                },
                "Rows": [{
                    "device_id": device_id,
                    "timestamp": datetime.now().isoformat(),
                    "latency_ms": device_data.get('latency', 0),
                    "cpu_percent": device_data.get('cpu_load_percent', 0),
                    "ram_percent": device_data.get('ram_percent', 0),
                    "temperature_c": get_temp(device_data),
                    "disk_percent": device_data.get('disk_percent', 0),
                    "status": device_data.get('status', 'online'),
                    "extended_sensors": json.dumps(device_data.get('extended_sensors', {}))
                }]
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/latency_history/Action",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Error agregando registro de latencia: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error en add_latency_record: {e}")
            return False
    
    def add_alert(self, device_data: Dict, alert_type: str, message: str, severity: str = "medium") -> bool:
        """Agregar alerta al sistema"""
        try:
            device_id = self.generate_device_id(device_data['pc_name'])
            
            payload = {
                "Action": "Add",
                "Properties": {
                    "Locale": "en-US"
                },
                "Rows": [{
                    "device_id": device_id,
                    "alert_type": alert_type,
                    "severity": severity,
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                    "resolved": False,
                    "pc_name": device_data['pc_name']
                }]
            }
            
            response = requests.post(
                f"{self.base_url}/apps/{self.app_id}/tables/alerts/Action",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(f"Alerta agregada para {device_data['pc_name']}: {message}")
                return True
            else:
                logger.error(f"Error agregando alerta: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error en add_alert: {e}")
            return False
    
    def get_device_history(self, pc_name: str, limit: int = 50, days: int = 7) -> List[Dict]:
        """Obtener historial de un dispositivo"""
        try:
            device_id = self.generate_device_id(pc_name)
            
            # Obtener todos los registros recientes
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
                json=payload
            )
            
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
                        filtered.append(row)
            
            # Ordenar por timestamp descendente y limitar
            filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"Error obteniendo historial para {pc_name}: {e}")
            return []
    
    def get_recent_alerts(self, limit: int = 20, unresolved_only: bool = True) -> List[Dict]:
        """Obtener alertas recientes"""
        try:
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
                json=payload
            )
            
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
            logger.error(f"Error obteniendo alertas: {e}")
            return []
    
    def get_system_stats(self, days: int = 1) -> Dict[str, Any]:
        """Obtener estadísticas del sistema"""
        try:
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
                json=payload
            )
            
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
                return {
                    'avg_latency': 0,
                    'avg_cpu': 0,
                    'total_records': 0,
                    'uptime_percent': 100,
                    'active_alerts': 0
                }
            
            # Calcular promedios
            latencies = [float(r.get('latency_ms', 0)) for r in recent_data if r.get('latency_ms')]
            cpus = [float(r.get('cpu_percent', 0)) for r in recent_data if r.get('cpu_percent')]
            
            # Calcular uptime
            total = len(recent_data)
            online = len([r for r in recent_data if r.get('status') == 'online'])
            uptime = (online / total * 100) if total > 0 else 100
            
            # Obtener alertas activas
            active_alerts = len(self.get_recent_alerts(limit=100, unresolved_only=True))
            
            return {
                'avg_latency': sum(latencies) / len(latencies) if latencies else 0,
                'avg_cpu': sum(cpus) / len(cpus) if cpus else 0,
                'total_records': len(recent_data),
                'uptime_percent': round(uptime, 1),
                'active_alerts': active_alerts
            }
            
        except Exception as e:
            logger.error(f"Error calculando estadísticas: {e}")
            return {
                'avg_latency': 0,
                'avg_cpu': 0,
                'total_records': 0,
                'uptime_percent': 0,
                'active_alerts': 0
            }
    
    def get_last_sync_time(self) -> Optional[datetime]:
        """Obtener última hora de sincronización"""
        return self.last_sync_time
