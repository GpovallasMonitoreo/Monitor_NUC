import os
import sys
import datetime
import random
import traceback
import asyncio
import json

current_file_path = os.path.abspath(__file__)
core_dir = os.path.dirname(current_file_path)
root_dir = os.path.dirname(core_dir)

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    import settings
    SUPABASE_URL = getattr(settings, "SUPABASE_URL", os.getenv("SUPABASE_URL"))
    SUPABASE_KEY = getattr(settings, "SUPABASE_KEY", os.getenv("SUPABASE_KEY"))
    print(f"✅ Configuración cargada correctamente.")
except ImportError as e:
    print(f"❌ Error importando settings: {e}")
    SUPABASE_URL = None
    SUPABASE_KEY = None

from supabase import create_client, Client

class Database:
    def __init__(self):
        self.url = SUPABASE_URL
        self.key = SUPABASE_KEY
        
        if not self.url or not self.key:
            print("⚠️ Faltan credenciales en settings.py")
            self.supabase: Client = None
        else:
            try:
                self.supabase: Client = create_client(self.url, self.key)
                print("✅ Conexión a Supabase establecida")
            except Exception as e:
                print(f"❌ Error conectando a Supabase: {e}")
                self.supabase = None

    def _map_keys(self, datos: dict) -> dict:
        """ Mapea claves a Supabase. Conservado intacto, se añadieron los de Drive. """
        mapeo = {
            "Ticket": "ticket_id", "ticket_id": "ticket_id", "Sitio": "sitio",
            "ID_TECNOLOGIA": "id_tecnologia", "id_tecnologia": "id_tecnologia",
            "Unidad de negocio": "unidad_negocio", "Unidad_de_negocio": "unidad_negocio",
            "Motivo_Capturado": "motivo_capturado", "Detalles_Extra": "detalles_extra",
            "Foto_URL": "foto_url", "foto_url": "foto_url",
            "Usuario_Reporta": "usuario_reporta", "Usuario_ID": "usuario_id",
            "Departamento_Reporta": "departamento_reporta", "Estatus": "estatus",
            "Prioridad": "prioridad", "Impacto": "impacto", "Urgencia": "urgencia",
            "se_notifico_a": "se_notifico_a", "Se notifico a:": "se_notifico_a",
            "Se_notifico_a": "se_notifico_a", "incidencia_causada_por": "incidencia_causada_por",
            "Incidencia causada por": "incidencia_causada_por", "Incidencia_causada_por": "incidencia_causada_por",
            "modificado_por": "modificado_por", "Modificado_Por": "modificado_por",
            "Quien_toma_la_incidencia": "quien_toma_incidencia", "quien_toma_la_incidencia": "quien_toma_incidencia",
            "quien_toma_incidencia": "quien_toma_incidencia", "Cerrado por": "cerrado_por",
            "cerrado_por": "cerrado_por", "Cerrado_por": "cerrado_por",
            "Causa_Raiz": "causa_raiz", "causa_raiz": "causa_raiz", "Causa": "causa_raiz",
            "Causa raíz": "causa_raiz", "Categoria_Principal": "categoria_principal",
            "categoria_principal": "categoria_principal", "Categoria": "categoria_principal",
            "Categoría Principal": "categoria_principal", "Incidencia": "incidencia",
            "incidencia": "incidencia", "Tipo_Incidencia": "incidencia", "Tipo Incidencia": "incidencia",
            "Área Causante de la Incidencia": "area_causante", "area_causante": "area_causante",
            "Area_Causante": "area_causante", "Área_Causante": "area_causante", "Area causante": "area_causante",
            "Descripcion_Solucion": "descripcion_solucion", "descripcion_solucion": "descripcion_solucion",
            "Solución Brindada": "solucion_brindada", "solucion_brindada": "solucion_brindada",
            "Solucion_Brindada": "solucion_brindada", "Solucion": "solucion_brindada",
            "Cómo se solucionó": "solucion_brindada", "Como se solucionó": "solucion_brindada",
            "foto_solucion": "testigo_solucion", "testigo_solucion": "testigo_solucion",
            "Testigo_Solucion": "testigo_solucion", "Foto_Solucion": "testigo_solucion",
            "Foto_Solucion_URL": "testigo_solucion", "foto_solucion_url": "testigo_solucion",
            "Testigo solución": "testigo_solucion", "Testigo Incidencia": "testigo_incidencia",
            "testigo_incidencia": "testigo_incidencia", "Testigo_Incidencia": "testigo_incidencia",
            "Foto_Incidencia": "foto_url", "Foto_Incidencia_URL": "foto_url", "foto_incidencia": "foto_url",
            "Fecha_Creacion": "fecha_creacion", "Fecha_Resolucion": "fecha_resolucion",
            "Hora_Inicio_Solucion": "hora_inicio_solucion", "Hora_Fin_Solucion": "hora_fin_solucion",
            "Tiempo_Solucion_Total": "tiempo_solucion_total", "Duracion_Real_Minutos": "duracion_real_minutos",
            "Tiempo_Minimo_SLA": "tiempo_minimo_sla", "Tiempo_SLA_Objetivo": "tiempo_sla_objetivo",
            "Tiempo_Fuera_SLA": "tiempo_fuera_sla", "Tiempo_SLA (HRS)": "tiempo_sla_hrs",
            "SLA_Horas": "sla_horas", "Tiempo_Real_Solucion": "tiempo_real_solucion",
            "SLA_Cumplido": "sla_cumplido", "sla_cumplido": "sla_cumplido",
            "Minutos_Excedidos": "minutos_excedidos", "SLA_Incumplido": "sla_incumplido",
            "sla_incumplido": "sla_incumplido", "Detalles del Equipo": "detalles_equipo",
            "detalles_equipo": "detalles_equipo", "Detalles_Equipo": "detalles_equipo", "Detalles equipo": "detalles_equipo",
            "Accion_Preventiva": "accion_preventiva", "accion_preventiva": "accion_preventiva", "Acción preventiva": "accion_preventiva",
            "Materiales_Utilizados": "materiales_utilizados", "materiales_utilizados": "materiales_utilizados",
            "Materiales": "materiales_utilizados", "Materiales utilizados": "materiales_utilizados",
            "Costo_Estimado": "costo_estimado", "Reincidencias": "reincidencias", "reincidencias": "reincidencias",
            "Reasignacion_1": "reasignacion_1", "Reasignacion_2": "reasignacion_2", "Reasignacion_3": "reasignacion_3",
            "Reasignacion_4": "reasignacion_4", "Reasignacion_5": "reasignacion_5",
            "Tecnico_Asignado": "tecnico_asignado", "Fecha_Modificacion": "fecha_modificacion", "fecha_modificacion": "fecha_modificacion",
            # 🆕 Nuevos campos para mapeo Drive
            "link_testigo_drive": "link_testigo_drive", "Link_Testigo_Drive": "link_testigo_drive",
            "tipo_registro": "tipo_registro"
        }
        
        datos_limpios = {}
        for key, value in datos.items():
            new_key = mapeo.get(key, key.lower().replace(" ", "_"))
            datos_limpios[new_key] = value
            
        return datos_limpios

    async def _generar_id_consecutivo(self):
        try:
            ahora = datetime.datetime.now()
            meses = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
            mes_str = meses[ahora.month - 1]
            anio_str = ahora.strftime("%y") 
            prefix = f"OPE{mes_str}{anio_str}"
            
            def _contar():
                return self.supabase.table("tickets").select("ticket_id", count="exact").ilike("ticket_id", f"{prefix}%").execute()
            
            res = await asyncio.to_thread(_contar)
            count = res.count if res.count is not None else 0
            consecutivo = count + 1
            ticket_id = f"{prefix}{consecutivo:02d}"
            print(f"🎫 ID generado: {ticket_id}")
            return ticket_id
        except Exception as e:
            print(f"⚠️ Error generando consecutivo: {e}")
            return f"OPE{random.randint(10000,99999)}"

    async def contar_reincidencias(self, sitio, motivo):
        try:
            def _query():
                return self.supabase.table("tickets").select("ticket_id", count="exact")\
                    .eq("sitio", sitio)\
                    .ilike("motivo_capturado", f"%{motivo}%")\
                    .execute()
            res = await asyncio.to_thread(_query)
            count = res.count if res.count is not None else 0
            reincidencias = count - 1 if count > 0 else 0
            return reincidencias
        except: return 0

    async def obtener_fecha_creacion(self, ticket_id):
        try:
            def _query():
                return self.supabase.table("tickets").select("fecha_creacion").eq("ticket_id", ticket_id).execute()
            res = await asyncio.to_thread(_query)
            if res.data and len(res.data) > 0: return res.data[0]['fecha_creacion']
            return None
        except: return None

    async def crear_ticket(self, datos):
        try:
            print(f"\n🎯 CREANDO NUEVO TICKET Y MULTIPLICANDO EN TABLAS")
            ticket_id = await self._generar_id_consecutivo()
            datos["Ticket"] = ticket_id
            
            ahora_iso = datetime.datetime.now().isoformat()
            datos["Fecha_Creacion"] = ahora_iso
            datos["hora_inicio_solucion"] = ahora_iso 

            if "ID_TECNOLOGIA" not in datos or not datos["ID_TECNOLOGIA"]:
                 datos["ID_TECNOLOGIA"] = "Pendiente"

            sla_horas = datos.get("SLA_Horas", "24")
            try: sla_num = float(str(sla_horas))
            except: sla_num = 24.0
            
            datos["SLA_Horas"] = sla_num
            datos["Tiempo_SLA (HRS)"] = sla_num
            datos["Tiempo_SLA_Objetivo"] = sla_num

            if "incidencia_causada_por" not in datos: datos["incidencia_causada_por"] = None
            if "se_notifico_a" not in datos: datos["se_notifico_a"] = datos.get("Departamento_Reporta", "")

            # 1. PREPARAR PAYLOAD LEGACY (Tabla: tickets)
            payload_legacy = self._map_keys(datos)

            # 2. PREPARAR PAYLOAD INCIDENCIAS GENERAL (Tabla: incidencias_general)
            payload_incidencias = {
                "ticket_id": ticket_id,
                "sitio_id": datos.get("Sitio", ""),
                "medio": datos.get("Unidad_de_negocio", ""),
                "motivo_incidencia": datos.get("Motivo_Capturado", ""),
                "detalles_extra": datos.get("Detalles_Extra", ""),
                "imagen_incidencia": datos.get("Foto_URL", ""),
                "link_testigo_drive": datos.get("link_testigo_drive", ""),
                "area_reporta": datos.get("Departamento_Reporta", ""),
                "estatus": "Abierto",
                "fecha_incidencia": datetime.datetime.now().strftime("%Y-%m-%d"),
                "hora_incidencia": datetime.datetime.now().strftime("%H:%M:%S")
            }

            # 3. PREPARAR PAYLOAD BIOBOX (Tabla: tickets_biobox)
            payload_biobox = payload_incidencias.copy()
            payload_biobox["tipo_registro"] = datos.get("tipo_registro", "Incidencia")

            print(f"\n🚀 INSERTANDO EN TABLAS...")
            
            # Ejecutar Inserciones en paralelo para no hacer lento el bot
            async def _insert_all():
                # Siempre inserta en legacy e incidencias_general
                self.supabase.table("tickets").insert(payload_legacy).execute()
                self.supabase.table("incidencias_general").insert(payload_incidencias).execute()
                # Si es BioBox, inserta también en tickets_biobox
                if payload_incidencias["medio"].upper() == "BIOBOX":
                    self.supabase.table("tickets_biobox").insert(payload_biobox).execute()

            await asyncio.to_thread(_insert_all)
            print(f"✅ Ticket sincronizado en todas las tablas: {ticket_id}")
            return ticket_id
                
        except Exception as e:
            print(f"\n❌ Error creando ticket: {e}")
            traceback.print_exc()
            return None

    async def actualizar_estatus(self, ticket_id, nuevo_estatus, datos_adicionales=None):
        try:
            print(f"\n🔄 Actualizando {ticket_id} a {nuevo_estatus} en TODAS las tablas")
            
            update_data_legacy = {"estatus": nuevo_estatus}
            ahora = datetime.datetime.now()
            update_data_legacy["fecha_modificacion"] = ahora.isoformat()
            
            if datos_adicionales:
                if "cerrado_por" in datos_adicionales and datos_adicionales["cerrado_por"]:
                    update_data_legacy["modificado_por"] = datos_adicionales["cerrado_por"]
                    update_data_legacy["cerrado_por"] = datos_adicionales["cerrado_por"]
                elif "modificado_por" in datos_adicionales and datos_adicionales["modificado_por"]:
                    update_data_legacy["modificado_por"] = datos_adicionales["modificado_por"]
                elif "usuario_reporta" in datos_adicionales and datos_adicionales["usuario_reporta"]:
                    update_data_legacy["modificado_por"] = datos_adicionales["usuario_reporta"]

            if nuevo_estatus in ["Resuelto", "Cerrado", "Resuelto y Cerrado", "Resuelto y cerrado"]:
                update_data_legacy["fecha_resolucion"] = ahora.isoformat()
                update_data_legacy["hora_fin_solucion"] = ahora.isoformat()
                fecha_creacion_str = await self.obtener_fecha_creacion(ticket_id)
                
                if fecha_creacion_str:
                    try:
                        fecha_creacion_str_clean = fecha_creacion_str.replace('Z', '+00:00')
                        fecha_creacion = datetime.datetime.fromisoformat(fecha_creacion_str_clean)
                        if fecha_creacion.tzinfo is None:
                            fecha_creacion = fecha_creacion.replace(tzinfo=datetime.timezone.utc)
                        ahora_tz = ahora.replace(tzinfo=datetime.timezone.utc)
                        
                        diff = ahora_tz - fecha_creacion
                        horas_totales = (diff.total_seconds() / 60) / 60
                        
                        update_data_legacy["duracion_real_minutos"] = int(diff.total_seconds() / 60)
                        update_data_legacy["tiempo_real_solucion"] = round(horas_totales, 2)
                        update_data_legacy["tiempo_solucion_total"] = f"{diff.days}d {int(diff.seconds // 3600)}h {int((diff.seconds % 3600) // 60)}m"
                        
                        sla_objetivo = 24.0
                        if datos_adicionales and "tiempo_sla_objetivo" in datos_adicionales:
                            try: sla_objetivo = float(datos_adicionales["tiempo_sla_objetivo"])
                            except: pass
                        
                        if horas_totales <= sla_objetivo:
                            update_data_legacy["sla_cumplido"] = True
                            update_data_legacy["sla_incumplido"] = "NO"
                            update_data_legacy["minutos_excedidos"] = 0
                            update_data_legacy["tiempo_fuera_sla"] = 0
                        else:
                            update_data_legacy["sla_cumplido"] = False
                            update_data_legacy["sla_incumplido"] = "SI"
                            exceso_horas = horas_totales - sla_objetivo
                            update_data_legacy["minutos_excedidos"] = int(exceso_horas * 60)
                            update_data_legacy["tiempo_fuera_sla"] = round(exceso_horas, 2)
                            
                    except Exception as e_time:
                        print(f"⚠️ Error calculando tiempos: {e_time}")
        
            if datos_adicionales:
                datos_limpios = self._map_keys(datos_adicionales)
                update_data_legacy.update(datos_limpios)

            # -------------------------------------------------------------
            # MAPEO PARA LAS NUEVAS TABLAS (incidencias_general y tickets_biobox)
            # -------------------------------------------------------------
            update_data_nuevas = {
                "estatus": nuevo_estatus,
                "solucion_brindada": update_data_legacy.get("solucion_brindada"),
                "causa_raiz": update_data_legacy.get("causa_raiz"),
                "categoria_principal": update_data_legacy.get("categoria_principal"),
                "imagen_solucion": update_data_legacy.get("testigo_solucion"),
                "tiempo_solucion_total": update_data_legacy.get("tiempo_solucion_total"),
                "impacto": update_data_legacy.get("impacto"),
                "origen": update_data_legacy.get("origen")
            }
            # Limpiar Nones del diccionario para no sobreescribir con nulos
            update_data_nuevas = {k: v for k, v in update_data_nuevas.items() if v is not None}
            
            if nuevo_estatus in ["Resuelto", "Cerrado", "Resuelto y Cerrado"]:
                update_data_nuevas["fecha_reparacion"] = ahora.strftime("%Y-%m-%d")
                update_data_nuevas["hora_reparacion"] = ahora.strftime("%H:%M:%S")

            def _update_all():
                # 1. Actualiza tabla Legacy
                res = self.supabase.table("tickets").update(update_data_legacy).eq("ticket_id", ticket_id).execute()
                # 2. Actualiza tabla Incidencias General
                self.supabase.table("incidencias_general").update(update_data_nuevas).eq("ticket_id", ticket_id).execute()
                # 3. Actualiza tabla Biobox (si existe ahí, la actualiza, si no, no pasa nada)
                self.supabase.table("tickets_biobox").update(update_data_nuevas).eq("ticket_id", ticket_id).execute()
                return res

            response = await asyncio.to_thread(_update_all)
            
            if response.data:
                print(f"✅ Ticket {ticket_id} actualizado en todas las tablas a '{nuevo_estatus}'")
                return True
            else:
                return False
                
        except Exception as e:
            print(f"\n❌ ERROR actualizando estatus: {e}")
            traceback.print_exc()
            return False

    async def registrar_reasignacion(self, ticket_id, nuevo_depto, motivo, usuario):
        try:
            print(f"\n🔄 PROCESANDO REASIGNACIÓN EN TODAS LAS TABLAS")
            
            def _select(): return self.supabase.table("tickets").select("*").eq("ticket_id", ticket_id).execute()
            resp = await asyncio.to_thread(_select)
            
            if not resp.data: return False
            ticket_data = resp.data[0]
            
            campo_reasignacion = "reasignacion_1"
            if ticket_data.get("reasignacion_1"): campo_reasignacion = "reasignacion_2"
            if ticket_data.get("reasignacion_2"): campo_reasignacion = "reasignacion_3"
            if ticket_data.get("reasignacion_3"): campo_reasignacion = "reasignacion_4"
            if ticket_data.get("reasignacion_4"): campo_reasignacion = "reasignacion_5"
            
            timestamp = datetime.datetime.now().strftime('%d/%m %H:%M')
            texto = f"{timestamp} | De: {ticket_data.get('departamento_reporta', 'N/A')} A: {nuevo_depto} | Por: {usuario} | Motivo: {motivo}"

            update_data_legacy = {
                "departamento_reporta": nuevo_depto,
                campo_reasignacion: texto,
                "modificado_por": usuario,
                "fecha_modificacion": datetime.datetime.now().isoformat(),
                "estatus": "Reasignado"
            }

            update_data_nuevas = {
                "es_reasignado": True,
                "area_responsable": nuevo_depto,
                "motivo_reasignacion": motivo,
                "fecha_reasignacion": datetime.datetime.now().strftime("%Y-%m-%d"),
                "hora_reasignacion": datetime.datetime.now().strftime("%H:%M:%S"),
                "estatus": "Reasignado"
            }

            def _update_all():
                res = self.supabase.table("tickets").update(update_data_legacy).eq("ticket_id", ticket_id).execute()
                self.supabase.table("incidencias_general").update(update_data_nuevas).eq("ticket_id", ticket_id).execute()
                self.supabase.table("tickets_biobox").update(update_data_nuevas).eq("ticket_id", ticket_id).execute()
                return res

            response = await asyncio.to_thread(_update_all)
            if response.data: return True
            return False
            
        except Exception as e:
            print(f"❌ Error en reasignación: {e}")
            return False

    # ---------------------------------------------------------
    # 🆕 FUNCIONES DE RUTAS Y BIOBOX (MANTENIDAS DEL PASO ANTERIOR)
    # ---------------------------------------------------------
    async def obtener_recorrido_biobox(self, tecnico: str):
        """Obtiene el progreso de la ruta basándose en los tickets de mantenimiento preventivo de hoy."""
        if not self.supabase: return None, None
        try:
            hoy = datetime.datetime.now().strftime('%Y-%m-%d')
            
            def _get_rutas():
                return self.supabase.table('rutas_tecnicos').select('sitio').ilike('tecnico', f"%{tecnico}%").execute()
            
            resp_rutas = await asyncio.to_thread(_get_rutas)
            sitios_asignados = [row['sitio'] for row in resp_rutas.data] if resp_rutas.data else []

            if not sitios_asignados: return None, None

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

# Instancia global de la base de datos
db = Database()
