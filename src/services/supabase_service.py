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

    # --- MÉTODOS DE MONITOREO (ORIGINALES - NO TOCAR) ---
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
            data_to_send = self.buffer
            self.client.table("raw_metrics").insert(data_to_send).execute()
            self.buffer = [] 
        except Exception as e:
            logger.error(f"❌ Error enviando batch a Supabase: {e}")
            self.buffer = []

    def upsert_device_status(self, device_data: dict):
        try:
            self.client.table("devices").upsert(device_data).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Error Supabase Upsert: {e}")
            return False

    def get_device_history(self, device_id, limit=50):
        try:
            response = self.client.table("raw_metrics")\
                .select("*")\
                .eq("device_id", device_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Error leyendo historial: {e}")
            return []

    def run_nightly_cleanup(self):
        try:
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            self.client.table("raw_metrics").delete().lt("created_at", cutoff).execute()
            logger.info("🧹 Limpieza mensual ejecutada.")
        except Exception as e:
            logger.error(f"Error en limpieza: {e}")

    # --- NUEVOS MÉTODOS PARA GESTIÓN DE PANTALLAS E INCIDENCIAS ---

    def get_all_assets(self):
        """Obtiene el inventario de pantallas para el Dashboard"""
        try:
            # Asumimos que tienes una tabla 'assets' o 'inventario_pantallas'
            # Si no existe, la crea o usa 'devices' con filtros
            response = self.client.table("assets").select("*").execute()
            return response.data
        except Exception as e:
            logger.error(f"Error obteniendo assets: {e}")
            return []

    def get_asset_by_id(self, asset_id):
        """Obtiene detalle de una pantalla específica"""
        try:
            # Busca por columna 'qtm' o 'id'
            response = self.client.table("assets").select("*").eq("qtm", asset_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error buscando asset {asset_id}: {e}")
            return None

    def register_new_asset(self, asset_data):
        """Registra una nueva instalación (Nueva Pantalla)"""
        try:
            # asset_data debe coincidir con las columnas de tu tabla 'assets' en Supabase
            response = self.client.table("assets").insert(asset_data).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error registrando asset: {e}")
            return None

    def get_incidents_by_site(self, site_name, limit=20):
        """
        Obtiene las incidencias reportadas (Discord -> Supabase).
        Usa el campo 'Sitio' o 'id_tecnologia' para filtrar.
        """
        try:
            # Nota: Ajusta 'incidencias' al nombre real de tu tabla de tickets en Supabase
            response = self.client.table("incidencias")\
                .select("*")\
                .ilike("sitio", f"%{site_name}%")\
                .order("fecha_creacion", desc=True)\
                .limit(limit)\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Error obteniendo incidencias para {site_name}: {e}")
            return []
