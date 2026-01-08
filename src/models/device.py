import logging
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from dateutil.tz import gettz as ZoneInfo

TZ_MX = ZoneInfo("America/Mexico_City")

class Device:
    def __init__(self, pc_name, **kwargs):
        self.pc_name = pc_name
        self.unit = kwargs.get('unit', 'Sin Asignar')
        self.ip_local = kwargs.get('ip', '0.0.0.0')
        
        self.cpu_load = 0.0
        self.ram_load = 0.0
        self.disk_load = 0.0
        self.temp_cpu = 0.0
        self.latency_ms = 0.0
        
        self.lat = kwargs.get('lat', 19.4326)
        self.lng = kwargs.get('lng', -99.1332)
        self.disconnections_count = kwargs.get('disconnections', 0)

        self.status = kwargs.get('status', 'unknown')
        self.last_seen = datetime.now(TZ_MX)

    def update_telemetry(self, data: dict):
        self.last_seen = datetime.now(TZ_MX)
        self.cpu_load = float(data.get('cpu_load_percent', 0))
        self.ram_load = float(data.get('ram_percent', 0))
        self.disk_load = float(data.get('disk_percent', 0))
        self.latency_ms = float(data.get('latency_ms', 0))
        
        if 'lat' in data: self.lat = float(data['lat'])
        if 'lng' in data: self.lng = float(data['lng'])

        sensors = data.get('sensors', {})
        self.temp_cpu = float(sensors.get('cpu_temp', 0))

        previous_status = self.status
        self._evaluate_status()

        if (self.status == 'critical' and previous_status != 'critical') or \
           (self.status == 'offline' and previous_status == 'online'):
            self.disconnections_count += 1

    def _evaluate_status(self):
        if self.temp_cpu > 85 or self.cpu_load > 95: self.status = 'critical'
        else: self.status = 'online'

    def to_dict(self):
        return {
            'pc_name': self.pc_name,
            'unit': self.unit,
            'ip': self.ip_local,
            'status': self.status,
            'lat': self.lat,
            'lng': self.lng,
            'disconnections': self.disconnections_count,
            'latency': self.latency_ms, # <--- Acceso directo para el mapa
            'metrics': {
                'cpu': self.cpu_load,
                'ram': self.ram_load,
                'temp': self.temp_cpu
            }
        }