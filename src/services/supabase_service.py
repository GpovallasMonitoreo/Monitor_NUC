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
            # Si faltan credenciales, lanzamos error para que __init__.py use el Stub
            raise ValueError("Faltan credenciales de Supabase en .env")

        self.client: Client = create_client(url, key)
        self.buffer = [] 
        self.BATCH_SIZE = 50 
        
        logger.info("✅ Conexión a Supabase establecida (Modo Batch)")

    def buffer_metric(self, device_id, latency, packet_loss=0):
        data = {
            "device_id": device_id,
            "latency_ms": int(latency) if latency is not None else 0,
            "packet_loss": int(packet_loss),
            "created_at": datetime.utcnow().isoformat()
        }
        self.buffer.append(data)
        
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

    def upsert_device_status(self, device_data: dict):
        """Actualiza el estado actual del dispositivo (Tabla inventario)"""
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
