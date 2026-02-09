"""
Conexión y operaciones con la base de datos Supabase
"""

import os
import sys
import datetime
import random
import traceback
import asyncio
import json

# Añadir rutas para imports
current_dir = os.path.dirname(os.path.abspath(__file__))
discord_bot_dir = os.path.dirname(current_dir)
src_dir = os.path.dirname(discord_bot_dir)
project_root = os.path.dirname(src_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"📊 Inicializando Database...")
print(f"📁 Ruta actual: {current_dir}")

try:
    import discord_bot.config.settings as settings
    SUPABASE_URL = getattr(settings, "SUPABASE_URL", os.getenv("SUPABASE_URL"))
    SUPABASE_KEY = getattr(settings, "SUPABASE_KEY", os.getenv("SUPABASE_KEY"))
    
    # Verificar credenciales
    if SUPABASE_URL and SUPABASE_KEY:
        print(f"✅ Configuración Supabase cargada")
        print(f"🔗 URL: {SUPABASE_URL[:40]}...")
    else:
        print("❌ ERROR: Credenciales de Supabase incompletas")
        print(f"   URL: {'✅' if SUPABASE_URL else '❌'}")
        print(f"   KEY: {'✅' if SUPABASE_KEY else '❌'}")
        
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
            print("❌ No se pueden inicializar credenciales de Supabase")
            self.supabase: Client = None
            return
        
        try:
            self.supabase: Client = create_client(self.url, self.key)
            print("✅ Conexión a Supabase establecida")
            
            # Test de conexión
            self._test_connection()
            
        except Exception as e:
            print(f"❌ Error conectando a Supabase: {e}")
            self.supabase = None
    
    def _test_connection(self):
        """Test simple de conexión a la base de datos"""
        try:
            test = self.supabase.table("tickets").select("ticket_id", count="exact").limit(1).execute()
            print(f"✅ Test de conexión exitoso. Tabla 'tickets' accesible")
            return True
        except Exception as e:
            print(f"⚠️ Test de conexión falló: {e}")
            return False
    
    def _map_keys(self, datos: dict) -> dict:
        """
        Mapea claves a Supabase. 
        """
        mapeo = {
            "Ticket": "ticket_id",
            "ticket_id": "ticket_id",
            "Sitio": "sitio",
            "ID_TECNOLOGIA": "id_tecnologia",
            "id_tecnologia": "id_tecnologia",
            "Unidad de negocio": "unidad_negocio",
            "Unidad_de_negocio": "unidad_negocio",
            "Motivo_Capturado": "motivo_capturado",
            "Detalles_Extra": "detalles_extra",
            "Foto_URL": "foto_url",
            "foto_url": "foto_url",
            "Usuario_Reporta": "usuario_reporta",
            "Usuario_ID": "usuario_id",
            "Departamento_Reporta": "departamento_reporta",
            "Estatus": "estatus",
            "Prioridad": "prioridad",
            "Impacto": "impacto",
            "Urgencia": "urgencia",
            
            # CAMPOS DE NOTIFICACIÓN
            "se_notifico_a": "se_notifico_a",
            "Se notifico a:": "se_notifico_a",
            "Se_notifico_a": "se_notifico_a",
            
            # CAMPOS DE INCIDENCIA
            "incidencia_causada_por": "incidencia_causada_por",
            "Incidencia causada por": "incidencia_causada_por",
            "Incidencia_causada_por": "incidencia_causada_por",
            
            # CAMPOS DE USUARIO
            "modificado_por": "modificado_por",
            "Modificado_Por": "modificado_por",
            
            "Quien_toma_la_incidencia": "quien_toma_incidencia", 
            "quien_toma_la_incidencia": "quien_toma_incidencia",
            "quien_toma_incidencia": "quien_toma_incidencia",
            
            "Cerrado por": "cerrado_por",
            "cerrado_por": "cerrado_por",
            "Cerrado_por": "cerrado_por",
            
            # CAMPOS DE SOLUCIÓN (CRÍTICOS)
            "Causa_Raiz": "causa_raiz",
            "causa_raiz": "causa_raiz",
            "Causa": "causa_raiz",
            "Causa raíz": "causa_raiz",
            
            "Categoria_Principal": "categoria_principal",
            "categoria_principal": "categoria_principal",
            "Categoria": "categoria_principal",
            "Categoría Principal": "categoria_principal",
            
            "Incidencia": "incidencia",
            "incidencia": "incidencia",
            "Tipo_Incidencia": "incidencia",
            "Tipo Incidencia": "incidencia",
            
            "Área Causante de la Incidencia": "area_causante",
            "area_causante": "area_causante",
            "Area_Causante": "area_causante",
            "Área_Causante": "area_causante",
            "Area causante": "area_causante",
            
            "Descripcion_Solucion": "descripcion_solucion",
            "descripcion_solucion": "descripcion_solucion",
            
            "Solución Brindada": "solucion_brindada",
            "solucion_brindada": "solucion_brindada",
            "Solucion_Brindada": "solucion_brindada",
            "Solucion": "solucion_brindada",
            "Cómo se solucionó": "solucion_brindada",
            "Como se solucionó": "solucion_brindada",
            
            # CAMPOS DE FOTOS
            "foto_solucion": "testigo_solucion", 
            "testigo_solucion": "testigo_solucion",
            "Testigo_Solucion": "testigo_solucion",
            "Foto_Solucion": "testigo_solucion",
            "Foto_Solucion_URL": "testigo_solucion",
            "foto_solucion_url": "testigo_solucion",
            "Testigo solución": "testigo_solucion",
            
            "Testigo Incidencia": "testigo_incidencia",
            "testigo_incidencia": "testigo_incidencia",
            "Testigo_Incidencia": "testigo_incidencia",
            "Foto_Incidencia": "foto_url",
            "Foto_Incidencia_URL": "foto_url",
            "foto_incidencia": "foto_url",
            
            # CAMPOS DE TIEMPO
            "Fecha_Creacion": "fecha_creacion",
            "Fecha_Resolucion": "fecha_resolucion",
            "Hora_Inicio_Solucion": "hora_inicio_solucion",
            "Hora_Fin_Solucion": "hora_fin_solucion",
            "Tiempo_Solucion_Total": "tiempo_solucion_total",
            "Duracion_Real_Minutos": "duracion_real_minutos",
            "Tiempo_Minimo_SLA": "tiempo_minimo_sla",
            "Tiempo_SLA_Objetivo": "tiempo_sla_objetivo",
            "Tiempo_Fuera_SLA": "tiempo_fuera_sla",
            "Tiempo_SLA (HRS)": "tiempo_sla_hrs",
            "SLA_Horas": "sla_horas",
            "Tiempo_Real_Solucion": "tiempo_real_solucion",
            "SLA_Cumplido": "sla_cumplido",
            "sla_cumplido": "sla_cumplido",
            "Minutos_Excedidos": "minutos_excedidos",
            "SLA_Incumplido": "sla_incumplido",
            "sla_incumplido": "sla_incumplido",
            
            # CAMPOS ADICIONALES
            "Detalles del Equipo": "detalles_equipo",
            "detalles_equipo": "detalles_equipo",
            "Detalles_Equipo": "detalles_equipo",
            "Detalles equipo": "detalles_equipo",
            
            "Accion_Preventiva": "accion_preventiva",
            "accion_preventiva": "accion_preventiva",
            "Acción preventiva": "accion_preventiva",
            
            "Materiales_Utilizados": "materiales_utilizados",
            "materiales_utilizados": "materiales_utilizados",
            "Materiales": "materiales_utilizados",
            "Materiales utilizados": "materiales_utilizados",
            
            "Costo_Estimado": "costo_estimado",
            "Reincidencias": "reincidencias",
            "reincidencias": "reincidencias",
            "Reasignacion_1": "reasignacion_1",
            "Reasignacion_2": "reasignacion_2",
            "Reasignacion_3": "reasignacion_3",
            "Reasignacion_4": "reasignacion_4",
            "Reasignacion_5": "reasignacion_5",
            "Tecnico_Asignado": "tecnico_asignado",
            "Fecha_Modificacion": "fecha_modificacion",
            "fecha_modificacion": "fecha_modificacion"
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
            print(f"🔁 Reincidencias para {sitio} - {motivo}: {reincidencias}")
            return reincidencias
        except Exception as e:
            print(f"⚠️ Error contando reincidencias: {e}")
            return 0

    async def obtener_fecha_creacion(self, ticket_id):
        try:
            def _query():
                return self.supabase.table("tickets").select("fecha_creacion").eq("ticket_id", ticket_id).execute()
            res = await asyncio.to_thread(_query)
            if res.data and len(res.data) > 0:
                fecha = res.data[0]['fecha_creacion']
                return fecha
            return None
        except Exception as e:
            print(f"❌ Error obteniendo fecha creación: {e}")
            return None

    async def crear_ticket(self, datos):
        try:
            print(f"\n🎯 CREANDO NUEVO TICKET")
            
            ticket_id = await self._generar_id_consecutivo()
            datos["Ticket"] = ticket_id
            
            ahora_iso = datetime.datetime.now().isoformat()
            datos["Fecha_Creacion"] = ahora_iso
            datos["hora_inicio_solucion"] = ahora_iso 

            if "ID_TECNOLOGIA" not in datos or not datos["ID_TECNOLOGIA"]:
                 datos["ID_TECNOLOGIA"] = "Pendiente"
                 print(f"🔄 ID_TECNOLOGIA establecido como 'Pendiente'")

            sla_horas = datos.get("SLA_Horas", "24")
            try: 
                sla_num = float(str(sla_horas))
            except: 
                sla_num = 24.0
            
            datos["SLA_Horas"] = sla_num
            datos["Tiempo_SLA (HRS)"] = sla_num
            datos["Tiempo_SLA_Objetivo"] = sla_num

            if "incidencia_causada_por" not in datos: 
                datos["incidencia_causada_por"] = None
                
            if "se_notifico_a" not in datos: 
                datos["se_notifico_a"] = datos.get("Departamento_Reporta", "")

            payload = self._map_keys(datos)

            print(f"\n🚀 INSERTANDO TICKET: {ticket_id}")
            def _insert():
                return self.supabase.table("tickets").insert(payload).execute()
            
            response = await asyncio.to_thread(_insert)
            
            if response.data:
                print(f"✅ Ticket creado exitosamente: {ticket_id}")
                return ticket_id
            else:
                print(f"❌ No se pudo crear el ticket {ticket_id}")
                return None
                
        except Exception as e:
            print(f"\n❌ Error creando ticket: {e}")
            traceback.print_exc()
            return None

    async def actualizar_estatus(self, ticket_id, nuevo_estatus, datos_adicionales=None):
        try:
            print(f"\n🔄 Actualizando {ticket_id} a {nuevo_estatus}")
            
            update_data = {"estatus": nuevo_estatus}
            ahora = datetime.datetime.now()
            
            # Siempre actualizar fecha_modificacion
            update_data["fecha_modificacion"] = ahora.isoformat()
            
            # Determinar quién modificó
            if datos_adicionales:
                if "cerrado_por" in datos_adicionales and datos_adicionales["cerrado_por"]:
                    update_data["modificado_por"] = datos_adicionales["cerrado_por"]
                    update_data["cerrado_por"] = datos_adicionales["cerrado_por"]
                elif "modificado_por" in datos_adicionales and datos_adicionales["modificado_por"]:
                    update_data["modificado_por"] = datos_adicionales["modificado_por"]
                elif "usuario_reporta" in datos_adicionales and datos_adicionales["usuario_reporta"]:
                    update_data["modificado_por"] = datos_adicionales["usuario_reporta"]

            # PARA ESTATUS "Resuelto" o "Cerrado"
            if nuevo_estatus in ["Resuelto", "Cerrado", "Resuelto y Cerrado", "Resuelto y cerrado"]:
                update_data["fecha_resolucion"] = ahora.isoformat()
                update_data["hora_fin_solucion"] = ahora.isoformat()
                
                # Obtener fecha de creación
                fecha_creacion_str = await self.obtener_fecha_creacion(ticket_id)
                
                if fecha_creacion_str:
                    try:
                        # Limpiar y parsear fecha
                        fecha_creacion_str_clean = fecha_creacion_str.replace('Z', '+00:00')
                        fecha_creacion = datetime.datetime.fromisoformat(fecha_creacion_str_clean)
                        
                        # Asegurar timezone
                        if fecha_creacion.tzinfo is None:
                            fecha_creacion = fecha_creacion.replace(tzinfo=datetime.timezone.utc)
                        
                        ahora_tz = ahora.replace(tzinfo=datetime.timezone.utc)
                        
                        # Calcular diferencia
                        diff = ahora_tz - fecha_creacion
                        
                        minutos_totales = diff.total_seconds() / 60
                        horas_totales = minutos_totales / 60
                        
                        update_data["duracion_real_minutos"] = int(minutos_totales)
                        update_data["tiempo_real_solucion"] = round(horas_totales, 2)
                        
                        dias = diff.days
                        hrs = int(diff.seconds // 3600)
                        mins = int((diff.seconds % 3600) // 60)
                        update_data["tiempo_solucion_total"] = f"{dias}d {hrs}h {mins}m"
                        
                        # Obtener SLA objetivo
                        sla_objetivo = 24.0  # default
                        if datos_adicionales and "tiempo_sla_objetivo" in datos_adicionales:
                            try:
                                sla_objetivo = float(datos_adicionales["tiempo_sla_objetivo"])
                            except:
                                pass
                        elif datos_adicionales and "sla_horas" in datos_adicionales:
                            try:
                                sla_objetivo = float(datos_adicionales["sla_horas"])
                            except:
                                pass
                        
                        # Verificar cumplimiento SLA
                        if horas_totales <= sla_objetivo:
                            update_data["sla_cumplido"] = True
                            update_data["sla_incumplido"] = "NO"
                            update_data["minutos_excedidos"] = 0
                            update_data["tiempo_fuera_sla"] = 0
                        else:
                            update_data["sla_cumplido"] = False
                            update_data["sla_incumplido"] = "SI"
                            exceso_horas = horas_totales - sla_objetivo
                            update_data["minutos_excedidos"] = int(exceso_horas * 60)
                            update_data["tiempo_fuera_sla"] = round(exceso_horas, 2)
                            
                    except Exception as e_time:
                        print(f"⚠️ Error calculando tiempos: {e_time}")
        
            # Agregar datos adicionales mapeados
            if datos_adicionales:
                datos_limpios = self._map_keys(datos_adicionales)
                update_data.update(datos_limpios)
        
            # Ejecutar actualización
            def _update():
                return self.supabase.table("tickets").update(update_data).eq("ticket_id", ticket_id).execute()

            response = await asyncio.to_thread(_update)
            
            if response.data:
                print(f"✅ Ticket {ticket_id} actualizado exitosamente a '{nuevo_estatus}'")
                return True
            else:
                print(f"⚠️ No se encontró el ticket {ticket_id} o no hubo cambios")
                return False
                
        except Exception as e:
            print(f"\n❌ ERROR actualizando estatus: {e}")
            traceback.print_exc()
            return False

    async def registrar_reasignacion(self, ticket_id, nuevo_depto, motivo, usuario):
        try:
            print(f"\n🔄 PROCESANDO REASIGNACIÓN")
            print(f"🎫 Ticket: {ticket_id}")
            
            def _select():
                return self.supabase.table("tickets").select("*").eq("ticket_id", ticket_id).execute()
            
            resp = await asyncio.to_thread(_select)
            
            if not resp.data:
                print(f"❌ Ticket {ticket_id} no encontrado")
                return False
                
            ticket_data = resp.data[0]
            
            # Determinar campo de reasignación a usar
            campo_reasignacion = "reasignacion_1"
            if ticket_data.get("reasignacion_1"): 
                campo_reasignacion = "reasignacion_2"
            if ticket_data.get("reasignacion_2"): 
                campo_reasignacion = "reasignacion_3"
            if ticket_data.get("reasignacion_3"): 
                campo_reasignacion = "reasignacion_4"
            if ticket_data.get("reasignacion_4"): 
                campo_reasignacion = "reasignacion_5"
            
            # Crear texto de reasignación
            timestamp = datetime.datetime.now().strftime('%d/%m %H:%M')
            texto = f"{timestamp} | De: {ticket_data.get('departamento_reporta', 'N/A')} A: {nuevo_depto} | Por: {usuario} | Motivo: {motivo}"

            update_data = {
                "departamento_reporta": nuevo_depto,
                campo_reasignacion: texto,
                "modificado_por": usuario,
                "fecha_modificacion": datetime.datetime.now().isoformat(),
                "estatus": "Reasignado"
            }

            def _update():
                return self.supabase.table("tickets").update(update_data).eq("ticket_id", ticket_id).execute()

            response = await asyncio.to_thread(_update)
            
            if response.data:
                print(f"✅ Reasignación completada exitosamente")
                return True
            else:
                print(f"⚠️ No se pudo actualizar la reasignación")
                return False
            
        except Exception as e:
            print(f"❌ Error en reasignación: {e}")
            traceback.print_exc()
            return False

# Instancia global de la base de datos
db = Database()
print("✅ Database module listo")
