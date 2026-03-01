import os
import asyncio
import datetime
from supabase import create_client, Client
import settings # Importa de core.settings

class Database:
    def __init__(self):
        self.url = getattr(settings, "SUPABASE_URL", os.getenv("SUPABASE_URL"))
        self.key = getattr(settings, "SUPABASE_KEY", os.getenv("SUPABASE_KEY"))
        
        if not self.url or not self.key:
            print("⚠️ Faltan credenciales de Supabase para el Bot.")
            self.supabase = None
        else:
            self.supabase: Client = create_client(self.url, self.key)
            print("✅ Conexión a Supabase establecida (Módulo Bot Operativo)")

    # ---------------------------------------------------------
    # FUNCIONES DE RUTAS Y BIOBOX
    # ---------------------------------------------------------
    async def obtener_recorrido_biobox(self, tecnico: str):
        """Obtiene el progreso de la ruta basándose en los tickets de mantenimiento preventivo de hoy."""
        if not self.supabase: return None, None
        
        try:
            hoy = datetime.datetime.now().strftime('%Y-%m-%d')
            
            # 1. Obtener sitios asignados al técnico en la tabla 'rutas_tecnicos'
            def _get_rutas():
                return self.supabase.table('rutas_tecnicos').select('sitio').ilike('tecnico', f"%{tecnico}%").execute()
            
            resp_rutas = await asyncio.to_thread(_get_rutas)
            sitios_asignados = [row['sitio'] for row in resp_rutas.data] if resp_rutas.data else []

            if not sitios_asignados:
                return None, None # No tiene ruta

            # 2. Buscar tickets de mantenimiento creados HOY para esos sitios
            def _get_tickets_hoy():
                return self.supabase.table('mantenimientos_preventivos') \
                    .select('sitio_id') \
                    .eq('fecha', hoy) \
                    .in_('sitio_id', sitios_asignados) \
                    .execute()

            resp_tickets = await asyncio.to_thread(_get_tickets_hoy)
            sitios_visitados = list(set([row['sitio_id'] for row in resp_tickets.data])) if resp_tickets.data else []
            sitios_pendientes = [s for s in sitios_asignados if s not in sitios_visitados]

            return sitios_visitados, sitios_pendientes
        except Exception as e:
            print(f"❌ Error DB obtener_recorrido: {e}")
            return [], []

# Instancia global para importar en los Cogs
db = Database()
