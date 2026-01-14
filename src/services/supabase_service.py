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

    def buffer_metric(self, device_id, latency, packet_loss=0, extra_data=None):
        """
        Guarda métricas en buffer para envío masivo.
        Acepta 'extra_data' con min_latency, max_latency, etc.
        """
        row = {
            "device_id": device_id,
            "latency_ms": int(latency) if latency is not None else 0,
            "packet_loss": int(packet_loss),
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Mapear datos extra a las columnas de SQL
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
            # Insertamos en raw_metrics
            self.client.table("raw_metrics").insert(data_to_send).execute()
            
            # Limpiamos buffer solo si tuvo éxito
            self.buffer = [] 
            
        except Exception as e:
            logger.error(f"❌ Error enviando batch a Supabase: {e}")
            # Estrategia simple: Si falla, limpiamos igual para no atascar la memoria RAM
            # En producción podrías implementar lógica de reintento
            self.buffer = []

    def upsert_device_status(self, device_data: dict):
        """Actualiza el inventario (Tabla devices)"""
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
        """Borra datos crudos viejos (Mantenimiento)"""
        try:
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            self.client.table("raw_metrics").delete().lt("created_at", cutoff).execute()
            logger.info("🧹 Limpieza mensual ejecutada.")
        except Exception as e:
            logger.error(f"Error en limpieza: {e}")
