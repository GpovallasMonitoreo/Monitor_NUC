import os
import requests
import json
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

# Configuración de Zona Horaria (Para que los logs salgan con hora de México)
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

TZ_MX = ZoneInfo("America/Mexico_City")
logger = logging.getLogger(__name__)

class AppSheetService:
    """
    Servicio AppSheet "Blindado".
    Convierte todo a Texto para evitar errores de tipo y maneja respuestas vacías.
    """
    
    # ==========================================================
    # 1. INICIALIZACIÓN Y CONFIGURACIÓN
    # ==========================================================
    def __init__(self):
        # Limpiamos espacios en blanco (.strip) por si el copy-paste de Render falló
        raw_key = os.getenv('APPSHEET_API_KEY', '')
        raw_id = os.getenv('APPSHEET_APP_ID', '')
        
        self.api_key = raw_key.strip()
        self.app_id = raw_id.strip()
        self.base_url = "https://api.appsheet.com/api/v2"
        
        # Verificación de encendido
        env_enabled = os.getenv('APPSHEET_ENABLED', 'false').lower()
        is_config_enabled = env_enabled in ['true', '1', 'yes', 'on']
        has_creds = len(self.api_key) > 5 and len(self.app_id) > 5

        if not is_config_enabled or not has_creds:
            self.enabled = False
            logger.warning("⚠️ AppSheetService Apagado (Faltan credenciales o flag enabled=false)")
            return
            
        self.enabled = True
        self.headers = {
            'Content-Type': 'application/json',
            'ApplicationAccessKey': self.api_key
        }
        self.last_sync_time = None
        logger.info(f"✅ AppSheetService Inicializado - App: ...{self.app_id[-4:]}")

    # ==========================================================
    # 2. MOTOR DE COMUNICACIÓN (El Corazón del Servicio)
    # ==========================================================
    def _make_safe_request(self, table: str, action: str, rows: List[Dict] = None, properties: Dict = None) -> Optional[Any]:
        """
        Envía la petición y maneja el error 'JSON Vacío' que te estaba pasando.
        """
        try:
            if not self.enabled: return None
            
            # Construcción del Payload estándar de AppSheet
            final_props = {"Locale": "es-MX", "Timezone": "Central Standard Time"}
            if properties: final_props.update(properties)

            payload = {
                "Action": action,
                "Properties": final_props
            }
            if rows: payload["Rows"] = rows
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            
            # Timeout de 30s es prudente para bases de datos
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            # --- CORRECCIÓN DEL ERROR "Expecting value..." ---
            if response.status_code == 200:
                self.last_sync_time = datetime.now(TZ_MX)
                
                # Si la respuesta está vacía (Content-Length 0), es un ÉXITO silencioso
                if not response.text or len(response.text.strip()) == 0:
                    return {"status": "success", "empty_response": True}
                
                # Si hay texto, intentamos parsear JSON
                try:
                    return response.json()
                except json.JSONDecodeError:
                    # Si devuelve 200 pero texto plano no-JSON
                    logger.warning(f"⚠️ AppSheet devolvió 200 OK pero no JSON en {table}")
                    return {"status": "success", "raw": response.text}
            
            # Si no es 200, es error real
            logger.error(f"❌ Error AppSheet {response.status_code} en {table}: {response.text}")
            return None
            
        except Exception as e:
            logger.error(f"🔥 Excepción conectando a AppSheet: {e}")
            return None

    def generate_device_id(self, pc_name: str) -> str:
        """Genera un ID consistente. Si es MX_XXXX lo usa, si no, genera Hash."""
        try:
            if not pc_name: return "UNKNOWN"
            clean = pc_name.strip().upper()
            # Si el nombre ya es un código de inventario (ej: MX_LUNA)
            if clean.startswith("MX_") and len(clean) > 4:
                 return clean.split(' ')[0].strip() # Toma solo la primera parte
            # Si es un nombre genérico (Desktop-...), crea un Hash único
            return f"HASH_{hashlib.md5(clean.encode()).hexdigest()[:10].upper()}"
        except: return "ERROR_ID"

    # ==========================================================
    # 3. TABLA DEVICES (MAESTRA)
    # ==========================================================
    def get_or_create_device(self, device_data: Dict) -> tuple:
        """Asegura que el dispositivo exista en la tabla maestra."""
        try:
            if not self.enabled: return False, None, False
            
            pc_name = str(device_data.get('pc_name', '')).strip()
            if not pc_name: return False, None, False
            
            device_id = self.generate_device_id(pc_name)
            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            # ESTRATEGIA TEXTO: Convertimos todo a string (str)
            row = {
                "device_id": device_id,          # KEY
                "pc_name": pc_name,              # Label
                "unit": str(device_data.get('unit', 'General')),
                "public_ip": str(device_data.get('public_ip', device_data.get('ip', ''))),
                "last_known_location": str(device_data.get('locName', pc_name)),
                "updated_at": ts
            }
            
            # Usamos 'Add' (AppSheet suele ignorar duplicados de Key en Add o actualizarlos)
            res = self._make_safe_request("devices", "Add", [row])
            return (res is not None), device_id, True
        except: return False, None, False

    # ==========================================================
    # 4. TABLA DEVICE_HISTORY (BITÁCORA)
    # ==========================================================
    def add_history_entry(self, log_data: Dict) -> bool:
        """
        Inserta ficha. 
        IMPORTANTE: Usa device_id como referencia, no el nombre.
        """
        try:
            if not self.enabled: return False
            pc_name = log_data.get('pc_name') or log_data.get('device_name')
            if not pc_name: return False

            # 1. Aseguramos que el padre (Device) exista
            success, device_id, _ = self.get_or_create_device({"pc_name": pc_name, "unit": log_data.get('unit')})
            if not success: 
                # Si falla crear el padre, igual intentamos (a veces ya existe)
                device_id = self.generate_device_id(pc_name)

            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            # ESTRATEGIA TEXTO + KEY REFERENCIADA
            row = {
                # Es buena práctica mandar un ID único para la fila del historial
                "history_id": str(uuid.uuid4()), 
                
                # REFERENCIA: Usamos el ID, no el nombre (Crucial para AppSheet)
                "device_id": device_id,
                
                # Columnas de Texto
                "action": str(log_data.get('action', 'Info')),
                "what": str(log_data.get('what', 'General')),
                "desc": str(log_data.get('desc', 'NA')),
                "exec": str(log_data.get('exec', 'Sistema')),
                
                # Booleanos como Texto ("true"/"false") es más seguro si la columna es Text
                "solved": str(log_data.get('solved', 'true')).lower(),
                
                "unit": str(log_data.get('unit', 'General')),
                "timestamp": ts
            }
            
            # Enviamos a 'device_history'
            res = self._make_safe_request("device_history", "Add", [row])
            return res is not None
        except Exception as e:
            logger.error(f"Error add_history: {e}")
            return False

    # ==========================================================
    # 5. TABLA LATENCY_HISTORY (MONITOREO)
    # ==========================================================
    def add_latency_to_history(self, data: Dict) -> bool:
        """Guarda métricas técnicas."""
        try:
            if not self.enabled: return False
            pc_name = data.get('pc_name', '')
            device_id = self.generate_device_id(pc_name)
            ts = datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            
            row = {
                "record_id": str(uuid.uuid4()),
                "device_id": device_id, # Referencia
                "timestamp": ts,
                # Convertimos números a string para evitar líos de decimales/puntos
                "latency_ms": str(data.get('latency', 0)),
                "cpu_load": str(data.get('cpu_load_percent', 0)),
                "ram_usage": str(data.get('ram_percent', 0)),
                "status": str(data.get('status', 'online'))
            }
            res = self._make_safe_request("latency_history", "Add", [row])
            return res is not None
        except: return False

    # ==========================================================
    # 6. TABLA ALERTS
    # ==========================================================
    def add_alert(self, data: Dict, type_alert: str, msg: str, sev: str) -> bool:
        try:
            if not self.enabled: return False
            device_id = self.generate_device_id(data.get('pc_name'))
            
            row = {
                "alert_id": str(uuid.uuid4()),
                "device_id": device_id,
                "alert_type": str(type_alert),
                "severity": str(sev),
                "message": str(msg),
                "timestamp": datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')
            }
            res = self._make_safe_request("alerts", "Add", [row])
            return res is not None
        except: return False

    # ==========================================================
    # 7. MÉTODOS DE LECTURA (Requeridos por api.py)
    # ==========================================================
    def get_full_history(self, limit: int = 50) -> List[Dict]:
        """Lee el historial. Usa 'Find'."""
        try:
            if not self.enabled: return []
            # Selector vacío = Traer todo
            res = self._make_safe_request("device_history", "Find", properties={"Top": limit})
            
            # Normalización: AppSheet devuelve lista o dict con key 'Rows'
            if res and isinstance(res, list): return res
            if res and isinstance(res, dict): return res.get('Rows', [])
            return []
        except: return []

    def get_history_for_device(self, pc_name: str) -> List[Dict]:
        """Lee historial filtrado por nombre de PC (requiere un Join implícito o filtro)"""
        try:
            if not self.enabled: return []
            # OJO: Si la tabla history tiene device_id, filtrar por pc_name es difícil directamente.
            # Filtramos por device_id mejor.
            dev_id = self.generate_device_id(pc_name)
            selector = f"Filter(device_history, [device_id] = '{dev_id}')"
            
            res = self._make_safe_request("device_history", "Find", properties={"Selector": selector})
            
            if res and isinstance(res, list): return res
            if res and isinstance(res, dict): return res.get('Rows', [])
            return []
        except: return []

    # ==========================================================
    # 8. MÉTODOS DE COMPATIBILIDAD Y DIAGNÓSTICO
    # ==========================================================
    def test_history_connection(self) -> bool:
        # Prueba leer 1 registro para ver si hay conexión
        res = self._make_safe_request("device_history", "Find", properties={"Top": 1})
        return res is not None

    def get_status_info(self) -> Dict:
        return {"status": "enabled", "last_sync": str(self.last_sync_time)}

    def get_system_stats(self) -> Dict:
        return {"status": "ok", "mode": "text-safe"}

    # Alias para que monitor_service no falle
    def sync_device_complete(self, data: Dict) -> bool: return self.get_or_create_device(data)[0]
    def upsert_device(self, data: Dict) -> bool: return self.get_or_create_device(data)[0]
    def add_latency_record(self, data: Dict) -> bool: return self.add_latency_to_history(data)
    def list_available_tables(self) -> List[str]: return ["devices", "device_history", "latency_history", "alerts"]
