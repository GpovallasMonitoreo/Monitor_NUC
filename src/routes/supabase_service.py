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
        self.buffer = [] # Buffer para acumular datos antes de enviar
        self.BATCH_SIZE = 50 # Enviar cada 50 registros para no saturar HTTP
        
        logger.info("✅ Conexión a Supabase establecida (Modo Batch)")

    def buffer_metric(self, device_id, latency, packet_loss=0):
        """
        No enviamos a la BD inmediatamente. Guardamos en memoria.
        Esto hace que tu app Python no se trabe esperando la red.
        """
        data = {
            "device_id": device_id,
            "latency_ms": int(latency) if latency is not None else 0,
            "packet_loss": int(packet_loss),
            "created_at": datetime.utcnow().isoformat()
        }
        self.buffer.append(data)
        
        # Si el buffer se llena, enviamos de golpe
        if len(self.buffer) >= self.BATCH_SIZE:
            self._flush_buffer()

    def _flush_buffer(self):
        """Envía todo lo acumulado a Supabase de una sola vez"""
        try:
            if not self.buffer: return
            
            # Insert masivo (bulk insert)
            data_to_send = self.buffer
            self.client.table("raw_metrics").insert(data_to_send).execute()
            
            logger.info(f"🚀 Enviados {len(data_to_send)} registros a Supabase")
            self.buffer = [] # Limpiar buffer
            
        except Exception as e:
            logger.error(f"❌ Error enviando batch a Supabase: {e}")
            # No limpiamos el buffer para reintentar en el siguiente ciclo

    def get_device_history(self, device_id, limit=50):
        """Obtiene historial reciente para el dashboard"""
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
        """
        EJECUTAR ESTO UNA VEZ AL DÍA (CRON JOB)
        1. Calcula promedios del día anterior.
        2. Guarda en 'daily_summary'.
        3. BORRA los datos 'raw' viejos para liberar espacio.
        """
        # Aquí iría lógica SQL compleja, pero para empezar, 
        # simplemente borremos lo que tenga más de 30 días para no llenar el GB.
        try:
            # Supabase Free no deja correr SQL crudo directamete desde el cliente a veces,
            # pero puedes llamar a una RPC (Stored Procedure).
            # Por ahora, simulamos una limpieza simple:
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            
            self.client.table("raw_metrics")\
                .delete()\
                .lt("created_at", cutoff)\
                .execute()
                
            logger.info("🧹 Limpieza mensual ejecutada: Datos viejos eliminados.")
        except Exception as e:
            logger.error(f"Error en limpieza: {e}")
