import os
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("Faltan credenciales de Supabase en .env")

        self.client: Client = create_client(url, key)
        self.buffer = [] 
        self.BATCH_SIZE = 50 
        
        logger.info("✅ Conexión a Supabase establecida (Modo Batch + Agregación)")

    # --- TUS FUNCIONES EXISTENTES (Buffer, Flush, etc.) ---
    def buffer_metric(self, device_id, latency, packet_loss=0, extra_data=None):
        row = {
            "device_id": device_id,
            "latency_ms": int(latency) if latency is not None else 0,
            "packet_loss": int(packet_loss),
            "created_at": datetime.utcnow().isoformat()
        }
        if extra_data:
            row['min_latency'] = extra_data.get('min')
            row['max_latency'] = extra_data.get('max')
            row['sample_count'] = extra_data.get('samples', 1)
        self.buffer.append(row)
        if len(self.buffer) >= self.BATCH_SIZE:
            self._flush_buffer()

    def _flush_buffer(self):
        try:
            if not self.buffer: return
            self.client.table("raw_metrics").insert(self.buffer).execute()
            self.buffer = [] 
        except Exception as e:
            logger.error(f"❌ Error batch Supabase: {e}")
            self.buffer = []

    def upsert_device_status(self, device_data: dict):
        try:
            self.client.table("devices").upsert(device_data).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Error Upsert: {e}")
            return False

    # --- NUEVA LÓGICA: GESTIÓN DE INCIDENCIAS Y MAPEO ---
    def get_device_incidents(self, qtm_id_or_site):
        """
        Obtiene incidencias mapeando los campos extraños de Discord a un formato limpio.
        """
        try:
            # Mapeo de campos (Tu diccionario original)
            mapeo_campos = {
                "Ticket": "ticket_id", "ticket_id": "ticket_id", "Sitio": "sitio",
                "ID_TECNOLOGIA": "id_tecnologia", "Unidad de negocio": "unidad_negocio",
                "Motivo_Capturado": "motivo_capturado", "Estatus": "estatus",
                "Prioridad": "prioridad", "Incidencia": "incidencia",
                "Solución Brindada": "solucion_brindada", "Costo_Estimado": "costo_estimado",
                "Fecha_Creacion": "fecha_creacion", "Foto_URL": "foto_url"
            }

            # Consulta a la tabla donde guardas lo de Discord (ej. 'incidencias')
            response = self.client.table("incidencias")\
                .select("*")\
                .or_(f"sitio.eq.{qtm_id_or_site},detalles_equipo.ilike.%{qtm_id_or_site}%")\
                .order("fecha_creacion", desc=True)\
                .execute()
            
            # Limpiar datos usando el mapeo
            clean_tickets = []
            for raw_ticket in response.data:
                clean_t = {}
                for key, val in raw_ticket.items():
                    # Si la llave está en el mapeo, usamos el nombre bonito, si no, la original
                    clean_key = mapeo_campos.get(key, key)
                    clean_t[clean_key] = val
                clean_tickets.append(clean_t)
                
            return clean_tickets
        except Exception as e:
            logger.error(f"❌ Error obteniendo incidencias: {e}")
            return []

    def register_manual_asset(self, asset_data: dict):
        """Registra activo desde Dashboard"""
        try:
            payload = {
                "pc_name": asset_data.get('pc_name'),
                "device_id": asset_data.get('qtm_id'),
                "status": "registered",
                "specs": asset_data.get('specs'),
                "investment": asset_data.get('investment', 0),
                "last_seen": datetime.utcnow().isoformat()
            }
            self.client.table("devices").upsert(payload).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Error registro manual: {e}")
            return False
