import discord
from discord import app_commands
from discord.ext import commands
import datetime
import traceback
import asyncio
import sys
import os
import importlib.util
import json
import random

# ==============================================================================
# 🛠️ CARGA DE CONFIGURACIÓN
# ==============================================================================
try:
    ruta_actual = os.path.dirname(__file__)
    ruta_config = os.path.abspath(os.path.join(ruta_actual, '..', 'settings.py'))
    
    if os.path.exists(ruta_config):
        spec = importlib.util.spec_from_file_location("settings", ruta_config)
        settings = importlib.util.module_from_spec(spec)
        sys.modules["settings"] = settings
        spec.loader.exec_module(settings)
        print(f"✅ Configuración cargada.")
    else:
        print(f"⚠️ No se encontró settings.py")
        settings = None
except Exception as e:
    settings = None

def get_conf(key, default):
    if settings and hasattr(settings, key):
        return getattr(settings, key)
    return default

COLOR_EMBED = get_conf('COLOR_EMBED', 0x3498DB)
COLOR_EXITO = get_conf('COLOR_EXITO', 0x2ECC71)
COLOR_ALERTA = get_conf('COLOR_ALERTA', 0xE74C3C)
COLOR_REASIGNADO = get_conf('COLOR_REASIGNADO', 0x9B59B6)
CANAL_GENERAL_ID = get_conf('CANAL_GENERAL_ID', 1457449842107220123)

# ==============================================================================
# IMPORTACIONES
# ==============================================================================
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import db
from core.locations import loc_manager
from utils.catalogo_data import CATALOGO_SOPORTE
from utils.texto import limpiar_texto

# ==============================================================================
# 📝 MODAL: CIERRE TÉCNICO
# ==============================================================================
class DetallesCierreModal(discord.ui.Modal, title="Detalles Técnicos de Cierre"):
    def __init__(self, view_instance, interaction_origin):
        super().__init__()
        self.view = view_instance
        self.interaction_origin = interaction_origin

        self.area_causante = discord.ui.TextInput(
            label="Área/Depto Causante",
            placeholder="Ej: Operaciones, TI, CFE, Vandalismo...",
            style=discord.TextStyle.short,
            required=True
        )
        self.detalles_equipo = discord.ui.TextInput(
            label="¿Qué se hizo al equipo?",
            placeholder="Ej: Cambio de NUC, reinicio físico...",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.materiales = discord.ui.TextInput(
            label="Materiales Utilizados",
            placeholder="Ej: Cable UTP, Cinta, Conectores...",
            style=discord.TextStyle.short,
            required=False
        )
        self.preventiva = discord.ui.TextInput(
            label="Acción Preventiva",
            placeholder="Ej: Se aseguró el anclaje...",
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.id_tecnologia = discord.ui.TextInput(
            label="ID Tecnología / Código Equipo",
            placeholder="Ej: NUC-484849856",
            style=discord.TextStyle.short,
            required=False
        )

        self.add_item(self.area_causante)
        self.add_item(self.detalles_equipo)
        self.add_item(self.materiales)
        self.add_item(self.preventiva)
        self.add_item(self.id_tecnologia)

    async def on_submit(self, interaction: discord.Interaction):
        self.view.datos_cierre = {
            "incidencia_causada_por": self.area_causante.value,
            "detalles_equipo": self.detalles_equipo.value,
            "materiales_utilizados": self.materiales.value,
            "accion_preventiva": self.preventiva.value,
            "id_tecnologia": self.id_tecnologia.value
        }
        await interaction.response.send_message(
            "📝 Datos guardados.\n📸 **ÚLTIMO PASO: Envía la FOTO DEL TESTIGO (Solución) a este chat ahora.**", 
            ephemeral=True
        )
        await self.view.esperar_foto(interaction)

# ==============================================================================
# 📝 MODALES Y VISTAS DE REPORTE
# ==============================================================================
class OtroMotivoModal(discord.ui.Modal, title="Detalles del Reporte"):
    def __init__(self, sitio, foto_url, cog_instance):
        super().__init__(timeout=300)
        self.sitio = sitio
        self.foto_url = foto_url
        self.cog = cog_instance
        self.descripcion = discord.ui.TextInput(label="Describe el problema", style=discord.TextStyle.paragraph, required=True, max_length=500)
        self.motivo_capturado = discord.ui.TextInput(label="Título breve", style=discord.TextStyle.short, required=True, max_length=100)
        self.add_item(self.descripcion)
        self.add_item(self.motivo_capturado)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            unidad_detectada = loc_manager.detectar_unidad(self.sitio)
            depto_asignado = get_conf('DEPTO_SOPORTE', "Soporte Remoto Digital")
            datos = {
                "sitio": self.sitio, "foto_url": self.foto_url, "unidad": unidad_detectada, "depto": depto_asignado,
                "motivo": "Otro", "motivo_capturado": self.motivo_capturado.value, "detalles_extra": self.descripcion.value,
                "usuario": interaction.user.display_name, "usuario_id": interaction.user.id
            }
            await self.cog.crear_ticket_final(interaction, datos)
        except: await interaction.followup.send("❌ Error.", ephemeral=True)

class ReasignarMotivoModal(discord.ui.Modal, title="Motivo de Reasignación"):
    def __init__(self, ticket_id, datos_originales, nueva_area, cog_instance):
        super().__init__()
        self.ticket_id = ticket_id
        self.datos = datos_originales
        self.nueva_area = nueva_area 
        self.cog = cog_instance
        self.campo_motivo = discord.ui.TextInput(label=f"¿Por qué reasignas a {nueva_area}?", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.campo_motivo)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        motivo_limpio = limpiar_texto(self.campo_motivo.value)
        await db.registrar_reasignacion(self.ticket_id, self.nueva_area, motivo_limpio, interaction.user.display_name)
        depto_anterior = self.datos['depto']
        self.datos['depto'] = self.nueva_area
        
        embed = discord.Embed(title=f"🔄 TICKET REASIGNADO", color=COLOR_REASIGNADO)
        embed.description = "**El ticket cambia de responsable.**"
        embed.add_field(name="📤 De", value=f"~~{depto_anterior}~~", inline=True)
        embed.add_field(name="📥 A", value=f"**{self.nueva_area}**", inline=True)
        embed.add_field(name="📝 Motivo", value=motivo_limpio, inline=False)
        embed.add_field(name="👤 Por", value=interaction.user.display_name, inline=False)
        await interaction.followup.send(embed=embed)
        await self.cog.notificar_nuevo_responsable(self.ticket_id, self.datos, motivo_limpio)

class ReasignarSeleccionView(discord.ui.View):
    def __init__(self, ticket_id, datos_ticket, cog_instance):
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
        self.datos = datos_ticket
        self.cog = cog_instance
        opciones = []
        deptos = get_conf('DEPARTAMENTOS', {})
        for nombre_depto, config in deptos.items():
            if nombre_depto != datos_ticket['depto']: opciones.append(discord.SelectOption(label=nombre_depto, emoji="➡️"))
        if not opciones: opciones.append(discord.SelectOption(label="Sin departamentos", value="N/A"))
        self.select_menu = discord.ui.Select(placeholder="Selecciona nuevo equipo...", options=opciones)
        self.select_menu.callback = self.callback_menu
        self.add_item(self.select_menu)

    async def callback_menu(self, interaction: discord.Interaction):
        area = self.select_menu.values[0]
        if area == "N/A": return
        await interaction.response.send_modal(ReasignarMotivoModal(self.ticket_id, self.datos, area, self.cog))

# ==============================================================================
# 🧙‍♂️ WIZARD DE RESOLUCIÓN
# ==============================================================================
class ResolucionWizardView(discord.ui.View):
    def __init__(self, ticket_id, cog_instance, datos_ticket, mensaje_controles):
        super().__init__(timeout=600)
        self.ticket_id = ticket_id
        self.cog = cog_instance
        self.datos_ticket = datos_ticket
        self.mensaje_controles = mensaje_controles
        self.datos_cierre = {}
        self.seleccion = {"categoria": None, "incidencia": None, "causa": None, "solucion": None, "foto_solucion": None}
        
        opciones_cat = []
        for cat in CATALOGO_SOPORTE.keys(): opciones_cat.append(discord.SelectOption(label=cat[:100], value=cat[:100]))
        self.sel_categoria = discord.ui.Select(placeholder="1️⃣ Selecciona Categoría Principal", options=opciones_cat[:25], custom_id="sel_cat")
        self.sel_categoria.callback = self.on_categoria_change
        self.add_item(self.sel_categoria)

    async def on_categoria_change(self, interaction: discord.Interaction):
        self.seleccion["categoria"] = self.sel_categoria.values[0]
        self.clear_items()
        self.add_item(self.sel_categoria)
        incidencias = list(CATALOGO_SOPORTE[self.seleccion["categoria"]].keys())
        opciones_inc = [discord.SelectOption(label=inc[:100], value=inc[:100]) for inc in incidencias[:25]]
        self.sel_incidencia = discord.ui.Select(placeholder="2️⃣ Tipo de Incidencia", options=opciones_inc, custom_id="sel_inc")
        self.sel_incidencia.callback = self.on_incidencia_change
        self.add_item(self.sel_incidencia)
        await interaction.response.edit_message(content=f"✅ Categoría: **{self.seleccion['categoria']}**\n📂 **Paso 2:** Selecciona la Incidencia:", view=self)

    async def on_incidencia_change(self, interaction: discord.Interaction):
        self.seleccion["incidencia"] = self.sel_incidencia.values[0]
        self.clear_items()
        self.add_item(self.sel_categoria)
        self.add_item(self.sel_incidencia)
        cat = self.seleccion["categoria"]
        inc = self.seleccion["incidencia"]
        causas = list(CATALOGO_SOPORTE[cat][inc].keys())
        opciones_causa = [discord.SelectOption(label=c[:100], value=c[:100]) for c in causas[:25]]
        self.sel_causa = discord.ui.Select(placeholder="3️⃣ Causa Raíz", options=opciones_causa, custom_id="sel_causa")
        self.sel_causa.callback = self.on_causa_change
        self.add_item(self.sel_causa)
        await interaction.response.edit_message(content=f"✅ Incidencia: **{self.seleccion['incidencia']}**\n🔍 **Paso 3:** ¿Cuál fue la causa?", view=self)

    async def on_causa_change(self, interaction: discord.Interaction):
        self.seleccion["causa"] = self.sel_causa.values[0]
        self.clear_items()
        self.add_item(self.sel_categoria)
        self.add_item(self.sel_incidencia)
        self.add_item(self.sel_causa)
        
        cat = self.seleccion["categoria"]
        inc = self.seleccion["incidencia"]
        cau = self.seleccion["causa"]
        nodo_data = CATALOGO_SOPORTE[cat][inc][cau]
        lista = nodo_data.get("soluciones", []) if isinstance(nodo_data, dict) else nodo_data
            
        opciones_sol = [discord.SelectOption(label=s[:100], value=s[:100]) for s in lista[:25]]
        self.sel_solucion = discord.ui.Select(placeholder="4️⃣ Pasos de Solución", options=opciones_sol, custom_id="sel_sol")
        self.sel_solucion.callback = self.on_solucion_change
        self.add_item(self.sel_solucion)
        await interaction.response.edit_message(content=f"✅ Causa: **{self.seleccion['causa']}**\n🛠️ **Paso 4:** ¿Cómo se solucionó?", view=self)

    async def on_solucion_change(self, interaction: discord.Interaction):
        self.seleccion["solucion"] = self.sel_solucion.values[0]
        await interaction.response.send_modal(DetallesCierreModal(self, interaction))

    async def esperar_foto(self, interaction: discord.Interaction):
        def check(m): return m.author == interaction.user and m.channel == interaction.channel and len(m.attachments) > 0
        try:
            mensaje_foto = await self.cog.bot.wait_for('message', check=check, timeout=120.0)
            self.seleccion["foto_solucion"] = mensaje_foto.attachments[0].url
            await self.finalizar_ticket(interaction)
        except asyncio.TimeoutError:
            try: await interaction.followup.send("❌ Tiempo agotado.", ephemeral=True)
            except: pass

    async def finalizar_ticket(self, interaction: discord.Interaction):
        try:
            if self.mensaje_controles: await self.mensaje_controles.edit(view=None, content="🔒 **Ticket Cerrado**")
        except: pass

        cat = self.seleccion["categoria"]
        inc = self.seleccion["incidencia"]
        cau = self.seleccion["causa"]
        
        try:
            nodo_data = CATALOGO_SOPORTE[cat][inc][cau]
            tiempos_sla = nodo_data["slas"].get(self.seleccion["solucion"], {"min": 24, "objetivo": 28, "max": 32})
        except:
            tiempos_sla = {"min": 24, "objetivo": 28, "max": 32}
        
        reincidencias = await db.contar_reincidencias(self.datos_ticket['sitio'], self.datos_ticket.get('motivo_capturado', ''))
        
        prioridad = "Media"
        urgencia = "Media"
        if "Pantalla" in inc or "Apagada" in inc:
             prioridad = "Alta"
             urgencia = "Alta"

        datos_resolucion = {
            "solucion_brindada": self.seleccion["solucion"],
            "causa_raiz": self.seleccion["causa"],
            "area_causante": self.datos_cierre.get("incidencia_causada_por", ""), 
            "incidencia_causada_por": self.seleccion["categoria"], 
            "categoria_principal": self.seleccion["categoria"],
            "incidencia": self.seleccion["incidencia"],
            "foto_solucion": self.seleccion["foto_solucion"], 
            "testigo_solucion": self.seleccion["foto_solucion"],
            "cerrado_por": interaction.user.display_name,
            "modificado_por": interaction.user.display_name,
            "quien_toma_incidencia": interaction.user.display_name,
            "descripcion_solucion": self.seleccion["solucion"],
            "tiempo_minimo_sla": tiempos_sla["min"],
            "tiempo_sla_objetivo": tiempos_sla["objetivo"],
            "tiempo_fuera_sla": tiempos_sla["max"],
            "id_tecnologia": self.datos_cierre.get("id_tecnologia", ""),
            "detalles_equipo": self.datos_cierre.get("detalles_equipo", ""),
            "materiales_utilizados": self.datos_cierre.get("materiales_utilizados", ""),
            "accion_preventiva": self.datos_cierre.get("accion_preventiva", ""),
            "reincidencias": reincidencias,
            "prioridad": prioridad,
            "urgencia": urgencia,
            "impacto": "Afectación de Servicio",
            "se_notifico_a": self.datos_ticket.get('depto', ''), 
        }
        
        await db.actualizar_estatus(self.ticket_id, "Resuelto", datos_resolucion)
        
        embed = discord.Embed(title="✅ TICKET RESUELTO Y CERRADO", color=COLOR_EXITO)
        embed.add_field(name="🆔 ID", value=self.ticket_id, inline=True)
        embed.add_field(name="🛠️ Solución", value=datos_resolucion['solucion_brindada'], inline=False)
        embed.add_field(name="🚨 Área Causante", value=datos_resolucion['area_causante'], inline=True)
        embed.add_field(name="📋 Detalles Equipo", value=datos_resolucion['detalles_equipo'], inline=False)
        if datos_resolucion['materiales_utilizados']:
             embed.add_field(name="📦 Materiales", value=datos_resolucion['materiales_utilizados'], inline=True)
        embed.add_field(name="👷 Cerrado por", value=interaction.user.display_name, inline=True)
        if datos_resolucion['foto_solucion']: embed.set_image(url=datos_resolucion['foto_solucion'])
        
        if isinstance(interaction.channel, discord.Thread): await interaction.channel.send(embed=embed)
        else: await interaction.followup.send(embed=embed)

        await self.cog.notificar_cierre_global(self.ticket_id, self.datos_ticket, datos_resolucion)
        await self.cerrar_hilo_fisico(interaction, embed)

    async def cerrar_hilo_fisico(self, interaction, embed_final):
        try:
            await asyncio.sleep(3)
            if isinstance(interaction.channel, discord.Thread): await interaction.channel.edit(archived=True, locked=True)
        except: pass

# ==============================================================================
# 🔘 BOTONES Y VISTAS PRINCIPALES (MODIFICADA)
# ==============================================================================
class AccionesTicketView(discord.ui.View):
    def __init__(self, ticket_id, datos_ticket, cog_instance, solo_reasignar=False, hilo_url=None):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.datos = datos_ticket
        self.cog = cog_instance
        
        # 🟢 LÓGICA DINÁMICA DE BOTONES
        if solo_reasignar:
            # Eliminar botón "Resolver" (es el primero)
            # Buscamos por custom_id por seguridad
            for child in self.children:
                if getattr(child, "custom_id", "") == "btn_resolver":
                    self.remove_item(child)
                    break
            
            # Agregar botón de enlace al hilo si existe
            if hilo_url:
                self.add_item(discord.ui.Button(label="🔗 Ir al Hilo del Ticket", style=discord.ButtonStyle.link, url=hilo_url))

    @discord.ui.button(label="✅ Resolver", style=discord.ButtonStyle.success, custom_id="btn_resolver")
    async def btn_resolver(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 🔒 DOBLE SEGURIDAD: RESTRICCIÓN DE HILOS
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("❌ **ACCIÓN DENEGADA:** Los tickets solo pueden resolverse dentro de su hilo correspondiente.", ephemeral=True)
            return

        await db.actualizar_estatus(self.ticket_id, "En Proceso", {"quien_toma_incidencia": interaction.user.display_name})
        view_wizard = ResolucionWizardView(self.ticket_id, self.cog, self.datos, interaction.message)
        await interaction.response.send_message("📂 **Asistente de Cierre:** Selecciona la categoría principal:", view=view_wizard, ephemeral=True)

    @discord.ui.button(label="🔄 Reasignar", style=discord.ButtonStyle.secondary, custom_id="btn_reasignar")
    async def btn_reasignar(self, interaction: discord.Interaction, button: discord.ui.Button):
        view_menu = ReasignarSeleccionView(self.ticket_id, self.datos, self.cog)
        await interaction.response.send_message("📍 **Reasignación:** Elige destino:", view=view_menu, ephemeral=True)

class SeleccionMotivoView(discord.ui.View):
    def __init__(self, sitio, foto_url, cog_instance):
        super().__init__(timeout=300)
        self.sitio = sitio
        self.foto_url = foto_url
        self.cog = cog_instance

    @discord.ui.select(placeholder="Selecciona el Motivo del Reporte", options=[
        discord.SelectOption(label="Pantalla Apagada", emoji="⚫"),
        discord.SelectOption(label="Pantalla Dañada", emoji="🔨"),
        discord.SelectOption(label="Grafiti", emoji="🎨"),
        discord.SelectOption(label="No se visualiza Pauta", emoji="🚫"),
        discord.SelectOption(label="Pauta Incorrecta", emoji="⚠️"),
        discord.SelectOption(label="Otro", emoji="❓")
    ])
    async def select_motivo(self, interaction: discord.Interaction, select: discord.ui.Select):
        motivo = select.values[0]
        if motivo == "Otro":
            await interaction.response.send_modal(OtroMotivoModal(self.sitio, self.foto_url, self.cog))
            return
        
        await interaction.response.defer(ephemeral=True)
        try:
            unidad_detectada = loc_manager.detectar_unidad(self.sitio)
            depto_asignado = get_conf('MAPA_MOTIVOS', {}).get(motivo, get_conf('DEPTO_SOPORTE', "Soporte Remoto Digital"))
            datos = {
                "sitio": self.sitio, "foto_url": self.foto_url, "unidad": unidad_detectada, "depto": depto_asignado,
                "motivo": motivo, "motivo_capturado": motivo, "seccion": "Reporte Inicial",
                "usuario": interaction.user.display_name, "usuario_id": interaction.user.id
            }
            await self.cog.crear_ticket_final(interaction, datos)
        except: await interaction.followup.send("❌ Error.", ephemeral=True)

# ==============================================================================
# ⚙️ COMANDO PRINCIPAL
# ==============================================================================
class SistemaTickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def sitio_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        try: return [app_commands.Choice(name=r, value=r) for r in loc_manager.buscar(current)]
        except: return []

    @app_commands.command(name="reporte", description="Reportar incidencia")
    @app_commands.describe(sitio="Busca la ubicación", foto="Evidencia obligatoria")
    @app_commands.autocomplete(sitio=sitio_autocomplete)
    async def reporte(self, interaction: discord.Interaction, sitio: str, foto: discord.Attachment):
        try:
            if not foto.content_type.startswith("image/"):
                await interaction.response.send_message("❌ Debe ser una imagen.", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            embed = discord.Embed(title="📋 Nuevo Reporte", description=f"📍 **Sitio:** {sitio}\n📂 **Selecciona el problema:**", color=COLOR_EMBED)
            embed.set_thumbnail(url=foto.url)
            await interaction.followup.send(embed=embed, view=SeleccionMotivoView(sitio, foto.url, self), ephemeral=True)
        except: await interaction.followup.send("❌ Error.", ephemeral=True)

    async def crear_ticket_final(self, interaction, datos):
        try:
            depto = datos.get('depto', '')
            sla_val = "4" if depto in [get_conf('DEPTO_SOPORTE', 'X'), get_conf('DEPTO_PAUTA', 'Y')] else "24"
            
            datos_db = {
                "Sitio": datos.get('sitio', ''),
                "Unidad_de_negocio": datos.get('unidad', ''),
                "Departamento_Reporta": datos.get('depto', ''),
                "Quien_toma_la_incidencia": "", 
                "Motivo_Capturado": datos.get('motivo_capturado', ''),
                "Detalles_Extra": datos.get('detalles_extra', ''),
                "Usuario_Reporta": datos.get('usuario', ''),
                "Usuario_ID": str(datos.get('usuario_id', '')),
                "Foto_URL": datos.get('foto_url', ''), 
                "Testigo_Incidencia": datos.get('foto_url', ''), 
                "Estatus": "Abierto",
                "SLA_Horas": sla_val
            }
            
            nuevo_id = await db.crear_ticket(datos_db)
            
            if nuevo_id:
                ahora = datetime.datetime.now()
                await interaction.followup.send(f"✅ **TICKET CREADO: {nuevo_id}**", ephemeral=True)
                datos['ticket_id'] = nuevo_id
                await self.crear_hilo_inicial(nuevo_id, datos)
            else:
                await interaction.followup.send("❌ Error DB.", ephemeral=True)
        except Exception as e:
            print(f"Error crear ticket: {e}")

    async def crear_hilo_inicial(self, ticket_id, datos):
        try:
            canal_general = self.bot.get_channel(CANAL_GENERAL_ID)
            if not canal_general: return
            
            embed = discord.Embed(title=f"🚨 Incidencia: {datos['unidad']}", color=COLOR_ALERTA)
            embed.add_field(name="🆔 Ticket", value=f"`{ticket_id}`", inline=True)
            embed.add_field(name="⚠️ Motivo", value=datos.get('motivo_capturado', ''), inline=True)
            embed.add_field(name="👷 Depto", value=datos['depto'], inline=True)
            embed.add_field(name="📍 Sitio", value=datos['sitio'], inline=False)
            if datos.get('detalles_extra'): embed.add_field(name="📝 Descripción", value=datos['detalles_extra'], inline=False)
            embed.add_field(name="👤 Reportó", value=datos['usuario'], inline=True)
            if datos.get('foto_url'): embed.set_image(url=datos['foto_url'])
            
            hilo = await canal_general.create_thread(name=f"🔴 {ticket_id} | {datos.get('motivo_capturado', '')[:30]}", type=discord.ChannelType.public_thread)
            
            # Dentro del Hilo: Vista Completa (Resolver + Reasignar)
            await hilo.send(embed=embed, view=AccionesTicketView(ticket_id, datos, self))
            
            if 'usuario_id' in datos: await hilo.send(f"<@{datos['usuario_id']}> ticket creado.")
            
            # Pasamos la URL del hilo para que aparezca en la notificación del grupo
            await self.notificar_nuevo_responsable(ticket_id, datos, hilo_url=hilo.jump_url)
        except Exception as e:
            print(f"❌ Error hilo: {e}")

    async def notificar_nuevo_responsable(self, ticket_id, datos, nota_extra="", hilo_url=None):
        try:
            deptos = get_conf('DEPARTAMENTOS', {})
            config_depto = deptos.get(datos['depto'])
            if config_depto:
                canal = self.bot.get_channel(config_depto['canal_id'])
                if canal:
                    embed = discord.Embed(title=f"🔔 Asignación: {ticket_id}", color=COLOR_EMBED)
                    embed.add_field(name="Sitio", value=datos['sitio'])
                    
                    # Notificación al Grupo: Vista Solo Reasignar + Link
                    view_grupo = AccionesTicketView(ticket_id, datos, self, solo_reasignar=True, hilo_url=hilo_url)
                    
                    await canal.send(f"<@&{config_depto['rol_id']}>", embed=embed, view=view_grupo)
        except: pass

    async def notificar_cierre_global(self, ticket_id, datos_ticket, datos_res):
        try:
            embed = discord.Embed(title=f"🏁 Resuelto: {ticket_id}", color=COLOR_EXITO)
            embed.add_field(name="Solución", value=datos_res['solucion_brindada'])
            embed.add_field(name="Cerrado por", value=datos_res['cerrado_por'])
            if datos_res.get('foto_solucion'): embed.set_thumbnail(url=datos_res['foto_solucion'])
            
            canal_general = self.bot.get_channel(CANAL_GENERAL_ID)
            if canal_general: await canal_general.send(embed=embed)

            deptos = get_conf('DEPARTAMENTOS', {})
            config_depto = deptos.get(datos_ticket['depto'])
            if config_depto:
                canal = self.bot.get_channel(config_depto['canal_id'])
                if canal: await canal.send(embed=embed)
        except: pass

async def setup(bot):
    await bot.add_cog(SistemaTickets(bot))