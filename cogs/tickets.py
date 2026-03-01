import discord
from discord import app_commands
from discord.ext import commands
import datetime
import traceback
import asyncio
import sys
import os
import importlib.util
import random

# ==============================================================================
# 🛠️ CARGA DE CONFIGURACIÓN
# ==============================================================================
try:
    ruta_actual = os.path.dirname(__file__)
    ruta_config = os.path.abspath(os.path.join(ruta_actual, '..', 'core', 'settings.py'))
    
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
# IMPORTACIONES DE CORE Y UTILS
# ==============================================================================
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.database import db
from utils.locations import LocationManager
from utils.catalogo_data import CATALOGO_SOPORTE
from utils.texto import limpiar_texto
from src.services.drive_service import DriveService  # 🆕 IMPORTACIÓN DE DRIVE

loc_manager = LocationManager()
drive_service = DriveService()  # 🆕 INSTANCIA DE DRIVE

# ==============================================================================
# 📝 MODALES AUXILIARES
# ==============================================================================
class OtroMotivoModal(discord.ui.Modal, title="Detalles del Reporte"):
    def __init__(self, sitio, foto_url, cog_instance, archivo_foto=None):
        super().__init__(timeout=300)
        self.sitio = sitio
        self.foto_url = foto_url
        self.archivo_foto = archivo_foto  # 🆕 Guardamos el objeto foto
        self.cog = cog_instance
        self.descripcion = discord.ui.TextInput(label="Describe el problema o mantenimiento", style=discord.TextStyle.paragraph, required=True, max_length=500)
        self.motivo_capturado = discord.ui.TextInput(label="Título breve", style=discord.TextStyle.short, required=True, max_length=100)
        self.add_item(self.descripcion)
        self.add_item(self.motivo_capturado)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            unidad_detectada = loc_manager.detectar_unidad(self.sitio)
            depto_asignado = get_conf('DEPTO_SOPORTE', "Soporte Remoto Digital")
            datos = {
                "sitio": self.sitio, 
                "foto_url": self.foto_url, 
                "archivo_foto": self.archivo_foto,  # 🆕 Pasamos el archivo
                "unidad": unidad_detectada, 
                "depto": depto_asignado,
                "motivo": "Otro", 
                "motivo_capturado": self.motivo_capturado.value, 
                "detalles_extra": self.descripcion.value,
                "usuario": interaction.user.display_name, 
                "usuario_id": interaction.user.id,
                "tipo_registro": "Incidencia"
            }
            await self.cog.crear_ticket_final(interaction, datos)
        except: 
            await interaction.followup.send("❌ Error.", ephemeral=True)

class OtraSolucionModal(discord.ui.Modal, title="Especificar Solución"):
    def __init__(self, wizard_view, interaction_origin):
        super().__init__()
        self.wizard = wizard_view
        self.solucion_personalizada = discord.ui.TextInput(
            label="¿Qué solución se aplicó?",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.solucion_personalizada)

    async def on_submit(self, interaction: discord.Interaction):
        self.wizard.seleccion["solucion"] = self.solucion_personalizada.value
        await interaction.response.send_message("📸 **Casi listo. Envía la FOTO de evidencia a este chat para cerrar el ticket.**", ephemeral=True)
        await self.wizard.esperar_foto(interaction)

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
        
        # Omitimos el await de db si no está implementado aún en tu database.py
        # await db.registrar_reasignacion(self.ticket_id, self.nueva_area, motivo_limpio, interaction.user.display_name)
        
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
# 🛡️ VALIDACIÓN DE INCIDENCIAS (EL FILTRO FINAL)
# ==============================================================================
class MotivoRechazoModal(discord.ui.Modal, title="Motivo de Rechazo"):
    def __init__(self, ticket_id, datos_ticket, cog_instance):
        super().__init__()
        self.ticket_id = ticket_id
        self.datos = datos_ticket
        self.cog = cog_instance
        self.motivo = discord.ui.TextInput(
            label="¿Por qué se rechaza la solución?",
            style=discord.TextStyle.paragraph,
            placeholder="Ej. La foto no es clara, falta información...",
            required=True
        )
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        motivo_limpio = limpiar_texto(self.motivo.value)
        texto_rechazo = f"Rechazado por {interaction.user.display_name}: {motivo_limpio}"
        
        # Regresar a Abierto y guardar el motivo en validacion_reasignacion
        await db.actualizar_estatus(self.ticket_id, "Abierto", {
            "validacion_reasignacion": texto_rechazo
        })
        
        # Eliminar el mensaje de validación del canal de incidencias
        try: await interaction.message.delete()
        except: pass

        embed = discord.Embed(title=f"❌ TICKET RECHAZADO: {self.ticket_id}", color=COLOR_ALERTA)
        embed.description = "**El departamento de Incidencias ha rechazado la solución.**"
        embed.add_field(name="📝 Motivo", value=motivo_limpio, inline=False)
        embed.add_field(name="👤 Validador", value=interaction.user.display_name, inline=True)
        
        await interaction.followup.send(f"✅ El ticket {self.ticket_id} ha sido devuelto a {self.datos.get('depto', 'su departamento')}.", ephemeral=True)
        
        # Notificar al departamento responsable que lo rechazaron
        await self.cog.notificar_rechazo(self.ticket_id, self.datos, embed)

class ValidacionIncidenciasView(discord.ui.View):
    def __init__(self, cog_instance):
        super().__init__(timeout=None) # Persistente
        self.cog = cog_instance

    @discord.ui.button(label="✅ Validar y Cerrar", style=discord.ButtonStyle.success, custom_id="btn_validar_cerrar")
    async def btn_validar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        embed = interaction.message.embeds[0]
        ticket_id = embed.fields[0].value.replace('`', '')
        
        # Cambiar el estado final a Cerrado
        await db.actualizar_estatus(ticket_id, "Cerrado", {
            "cerrado_por": interaction.user.display_name,
            "validacion_reasignacion": "Validado Correctamente"
        })
        
        # Actualizar el mensaje en el canal de incidencias
        embed.color = COLOR_EXITO
        embed.title = f"🔒 TICKET CERRADO: {ticket_id}"
        embed.add_field(name="✅ Validado por", value=interaction.user.display_name, inline=False)
        await interaction.message.edit(embed=embed, view=None) # Quitamos los botones
        
        # Avisar globalmente que ya se cerró definitivamente
        canal_general = self.cog.bot.get_channel(CANAL_GENERAL_ID)
        if canal_general:
            await canal_general.send(f"🎉 El ticket **{ticket_id}** ha sido validado y cerrado oficialmente por {interaction.user.display_name}.")

    @discord.ui.button(label="❌ Rechazar (Reabrir)", style=discord.ButtonStyle.danger, custom_id="btn_rechazar_validacion")
    async def btn_rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        ticket_id = embed.fields[0].value.replace('`', '')
        
        # Reconstruir datos mínimos para saber a quién avisar
        depto_original = "Soporte Remoto Digital" # Valor por defecto
        for field in embed.fields:
            if field.name == "👷 Depto": 
                depto_original = field.value
                break
            
        datos_ticket = {"depto": depto_original, "ticket_id": ticket_id}
        
        # Abrir el modal pidiendo la razón
        await interaction.response.send_modal(MotivoRechazoModal(ticket_id, datos_ticket, self.cog))

# ==============================================================================
# 🧙‍♂️ WIZARD DE RESOLUCIÓN (SIN MODAL FINAL)
# ==============================================================================
class ResolucionWizardView(discord.ui.View):
    def __init__(self, ticket_id, cog_instance, datos_ticket, mensaje_controles):
        super().__init__(timeout=600)
        self.ticket_id = ticket_id
        self.cog = cog_instance
        self.datos_ticket = datos_ticket
        self.mensaje_controles = mensaje_controles
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
            
        opciones_sol = [discord.SelectOption(label=s[:100], value=s[:100]) for s in lista[:24]]
        # Agregamos la opción de capturar manualmente si no está en catálogo
        opciones_sol.append(discord.SelectOption(label="Otra solución (Escribir...)", value="OTRA_SOLUCION", emoji="✏️"))

        self.sel_solucion = discord.ui.Select(placeholder="4️⃣ Solución Aplicada", options=opciones_sol, custom_id="sel_sol")
        self.sel_solucion.callback = self.on_solucion_change
        self.add_item(self.sel_solucion)
        await interaction.response.edit_message(content=f"✅ Causa: **{self.seleccion['causa']}**\n🛠️ **Paso 4:** ¿Cómo se solucionó?", view=self)

    async def on_solucion_change(self, interaction: discord.Interaction):
        if self.sel_solucion.values[0] == "OTRA_SOLUCION":
            await interaction.response.send_modal(OtraSolucionModal(self, interaction))
        else:
            self.seleccion["solucion"] = self.sel_solucion.values[0]
            await interaction.response.send_message("📸 **¡Perfecto! Envía la FOTO DEL TESTIGO (Solución) a este chat para finalizar.**", ephemeral=True)
            await self.esperar_foto(interaction)

    async def esperar_foto(self, interaction: discord.Interaction):
        def check(m): return m.author == interaction.user and m.channel == interaction.channel and len(m.attachments) > 0
        try:
            mensaje_foto = await self.cog.bot.wait_for('message', check=check, timeout=120.0)
            self.seleccion["foto_solucion"] = mensaje_foto.attachments[0].url
            
            # 🆕 También guardamos el objeto attachment para subirlo a Drive
            self.seleccion["archivo_foto_solucion"] = mensaje_foto.attachments[0]
            
            await self.finalizar_ticket(interaction)
        except asyncio.TimeoutError:
            try: await interaction.followup.send("❌ Tiempo agotado para subir la foto.", ephemeral=True)
            except: pass

    async def finalizar_ticket(self, interaction: discord.Interaction):
        try:
            if self.mensaje_controles: await self.mensaje_controles.edit(view=None, content="🔒 **Ticket Cerrado**")
        except: pass

        cat = self.seleccion["categoria"]
        inc = self.seleccion["incidencia"]
        cau = self.seleccion["causa"]
        
        # Autofill inteligente desde Catálogo (Sin modal final)
        try:
            nodo_data = CATALOGO_SOPORTE[cat][inc][cau]
            tiempos_sla = nodo_data["slas"].get(self.seleccion["solucion"], {"min": 24, "objetivo": 28, "max": 32})
        except:
            tiempos_sla = {"min": 24, "objetivo": 28, "max": 32}
        
        prioridad = "Media"
        urgencia = "Media"
        impacto = "Afectación de Servicio"
        origen = "Interno"

        if "Pantalla" in inc or "Apagada" in inc or "Robo" in inc:
             prioridad = "Alta"
             urgencia = "Alta"
             impacto = "Comercial / Cliente"
        if "Mantenimiento" in cat:
             prioridad = "Baja"
             urgencia = "Baja"
             impacto = "Presencia del Medio"

        # 🆕 Subir foto de solución a Drive si existe
        link_drive_solucion = self.seleccion.get("foto_solucion")
        if self.seleccion.get("archivo_foto_solucion"):
            await interaction.edit_original_response(content="☁️ Subiendo evidencia de solución a Google Drive...")
            link_drive_solucion = await drive_service.subir_imagen_ticket(
                self.seleccion["archivo_foto_solucion"], 
                f"{self.ticket_id}-solucion"
            )

        datos_resolucion = {
            "solucion_brindada": self.seleccion["solucion"],
            "causa_raiz": self.seleccion["causa"],
            "categoria_principal": self.seleccion["categoria"],
            "incidencia": self.seleccion["incidencia"],
            "foto_solucion": self.seleccion["foto_solucion"], 
            "link_testigo_drive_solucion": link_drive_solucion,  # 🆕 URL de Drive para solución
            "testigo_solucion": self.seleccion["foto_solucion"],
            "cerrado_por": interaction.user.display_name,
            "tiempo_minimo_sla": tiempos_sla["min"],
            "tiempo_sla_objetivo": tiempos_sla["objetivo"],
            "tiempo_fuera_sla": tiempos_sla["max"],
            "prioridad": prioridad,
            "urgencia": urgencia,
            "impacto": impacto,
            "origen": origen,
            "estatus": "Resuelto"
        }
        
        # Actualizar en BD
        # await db.actualizar_estatus(self.ticket_id, "Resuelto", datos_resolucion)
        
        embed = discord.Embed(title="✅ TICKET RESUELTO Y CERRADO", color=COLOR_EXITO)
        embed.add_field(name="🆔 ID", value=self.ticket_id, inline=True)
        embed.add_field(name="🛠️ Solución", value=datos_resolucion['solucion_brindada'], inline=False)
        embed.add_field(name="📊 Impacto", value=datos_resolucion['impacto'], inline=True)
        embed.add_field(name="👷 Cerrado por", value=interaction.user.display_name, inline=True)
        
        # Mostrar link de Drive si existe
        if link_drive_solucion and link_drive_solucion != self.seleccion.get("foto_solucion"):
            embed.add_field(name="📂 Respaldo Drive", value=f"[Abrir imagen]({link_drive_solucion})", inline=False)
        
        if datos_resolucion['foto_solucion']: 
            embed.set_image(url=datos_resolucion['foto_solucion'])
        
        if isinstance(interaction.channel, discord.Thread): 
            await interaction.channel.send(embed=embed)
        else: 
            await interaction.followup.send(embed=embed)

        # ===== SECCIÓN: VALIDACIÓN POR INCIDENCIAS =====
        # 1. Enviar alerta al hilo del técnico
        if isinstance(interaction.channel, discord.Thread):
            await interaction.channel.send("⏳ **La solución ha sido enviada al departamento de Incidencias para su validación.** El hilo se bloqueará temporalmente.")
        else:
            await interaction.followup.send("⏳ Solución enviada a validación.", ephemeral=True)

        # 2. Enviar la tarjeta de Validación al canal de Incidencias
        try:
            deptos = get_conf('DEPARTAMENTOS', {})
            canal_incidencias_id = deptos.get(get_conf('DEPTO_INCIDENCIAS', 'Incidencias'), {}).get('canal_id')
            
            # Si no está en DEPARTAMENTOS, usar un ID por defecto
            if not canal_incidencias_id:
                canal_incidencias_id = get_conf('CANAL_INCIDENCIAS_ID', None)
                
            canal_inc = self.cog.bot.get_channel(canal_incidencias_id)
            
            if canal_inc:
                # Armamos la tarjeta para las validadoras
                embed_val = discord.Embed(title=f"🔎 VALIDACIÓN REQUERIDA: {self.ticket_id}", color=0xF1C40F)
                embed_val.add_field(name="🆔 Ticket", value=f"`{self.ticket_id}`", inline=True)
                embed_val.add_field(name="🛠️ Solución Aplicada", value=datos_resolucion['solucion_brindada'], inline=False)
                embed_val.add_field(name="👷 Depto", value=self.datos_ticket.get('depto', 'Desconocido'), inline=True)
                embed_val.add_field(name="🔧 Técnico", value=interaction.user.display_name, inline=True)
                embed_val.add_field(name="📍 Sitio", value=self.datos_ticket.get('sitio', 'No especificado'), inline=True)
                
                # Link a Drive si existe
                if link_drive_solucion and link_drive_solucion != self.seleccion.get("foto_solucion"):
                    embed_val.add_field(name="📂 Evidencia Drive", value=f"[Abrir]({link_drive_solucion})", inline=False)
                
                if datos_resolucion.get('foto_solucion'): 
                    embed_val.set_image(url=datos_resolucion['foto_solucion'])
                
                # Obtener el rol de incidencias
                rol_incidencias_id = deptos.get(get_conf('DEPTO_INCIDENCIAS', 'Incidencias'), {}).get('rol_id')
                if rol_incidencias_id:
                    contenido = f"🔔 <@&{rol_incidencias_id}> ¡Hay un ticket esperando revisión!"
                else:
                    contenido = "🔔 ¡Hay un ticket esperando revisión!"
                
                await canal_inc.send(
                    content=contenido, 
                    embed=embed_val, 
                    view=ValidacionIncidenciasView(self.cog)
                )
        except Exception as e:
            print(f"❌ Error al enviar a Incidencias: {e}")

        # Bloquear el hilo para que no escriban mientras se valida
        await self.cerrar_hilo_fisico(interaction, embed)

        # await self.cog.notificar_cierre_global(self.ticket_id, self.datos_ticket, datos_resolucion)

    async def cerrar_hilo_fisico(self, interaction, embed_final):
        try:
            await asyncio.sleep(3)
            if isinstance(interaction.channel, discord.Thread): 
                await interaction.channel.edit(archived=True, locked=True)
        except: pass

# ==============================================================================
# 🔘 VISTAS PERSISTENTES GLOBALES (Sobreviven a reinicios)
# ==============================================================================
class AccionesTicketGlobalView(discord.ui.View):
    def __init__(self, cog_instance):
        # timeout=None hace que la vista no caduque nunca
        super().__init__(timeout=None)
        self.cog = cog_instance

    # custom_id estáticos para que Discord los reconozca al reiniciar
    @discord.ui.button(label="✅ Resolver", style=discord.ButtonStyle.success, custom_id="btn_resolver_global")
    async def btn_resolver(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("❌ **ACCIÓN DENEGADA:** Resuelve el ticket dentro de su hilo.", ephemeral=True)
            return
            
        # Reconstruir datos de forma Stateless (leyendo el Embed del mensaje original)
        embed = interaction.message.embeds[0]
        ticket_id = embed.fields[0].value.replace('`', '')
        motivo = embed.fields[1].value
        depto = embed.fields[2].value
        sitio = embed.fields[3].value
        
        datos_reconstruidos = {
            "ticket_id": ticket_id, "sitio": sitio, "depto": depto, "motivo_capturado": motivo
        }

        # await db.actualizar_estatus(ticket_id, "En Proceso", {"quien_toma_incidencia": interaction.user.display_name})
        view_wizard = ResolucionWizardView(ticket_id, self.cog, datos_reconstruidos, interaction.message)
        await interaction.response.send_message("📂 **Asistente de Cierre:** Selecciona la categoría principal:", view=view_wizard, ephemeral=True)

    @discord.ui.button(label="🔄 Reasignar", style=discord.ButtonStyle.secondary, custom_id="btn_reasignar_global")
    async def btn_reasignar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        ticket_id = embed.fields[0].value.replace('`', '')
        datos_reconstruidos = {"depto": embed.fields[2].value}

        view_menu = ReasignarSeleccionView(ticket_id, datos_reconstruidos, self.cog)
        await interaction.response.send_message("📍 **Reasignación:** Elige el nuevo destino:", view=view_menu, ephemeral=True)

class SeleccionMotivoView(discord.ui.View):
    def __init__(self, sitio, foto_url, cog_instance):
        super().__init__(timeout=300)
        self.sitio = sitio
        self.foto_url = foto_url
        self.cog = cog_instance
        self.archivo_foto = None  # Se asignará después

    @discord.ui.select(placeholder="Selecciona el Motivo del Reporte", options=[
        discord.SelectOption(label="Pantalla Apagada", emoji="⚫"),
        discord.SelectOption(label="Pantalla Dañada", emoji="🔨"),
        discord.SelectOption(label="Grafiti", emoji="🎨"),
        discord.SelectOption(label="No se visualiza Pauta", emoji="🚫"),
        discord.SelectOption(label="Pauta Incorrecta", emoji="⚠️"),
        discord.SelectOption(label="Mantenimiento Preventivo", emoji="🛠️", description="Limpieza, revisión, ajustes"),
        discord.SelectOption(label="Otro", emoji="❓")
    ])
    async def select_motivo(self, interaction: discord.Interaction, select: discord.ui.Select):
        motivo = select.values[0]
        if motivo == "Otro":
            # 🆕 Pasamos también el archivo al modal
            await interaction.response.send_modal(OtroMotivoModal(self.sitio, self.foto_url, self.cog, self.archivo_foto))
            return
        
        await interaction.response.defer(ephemeral=True)
        try:
            unidad_detectada = loc_manager.detectar_unidad(self.sitio)
            depto_asignado = get_conf('MAPA_MOTIVOS', {}).get(motivo, get_conf('DEPTO_SOPORTE', "Soporte Remoto Digital"))
            
            tipo_registro = "Mantenimiento Preventivo" if motivo == "Mantenimiento Preventivo" else "Incidencia"

            datos = {
                "sitio": self.sitio, 
                "foto_url": self.foto_url,
                "archivo_foto": self.archivo_foto,  # 🆕 Pasamos el archivo
                "unidad": unidad_detectada, 
                "depto": depto_asignado,
                "motivo": motivo, 
                "motivo_capturado": motivo, 
                "seccion": "Reporte Inicial",
                "usuario": interaction.user.display_name, 
                "usuario_id": interaction.user.id,
                "tipo_registro": tipo_registro
            }
            await self.cog.crear_ticket_final(interaction, datos)
        except Exception as e: 
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

# ==============================================================================
# ⚙️ COMANDO PRINCIPAL Y REGISTRO
# ==============================================================================
class SistemaTickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # 🟢 Registramos las vistas para que sobrevivan a reinicios
        self.bot.add_view(AccionesTicketGlobalView(self))
        self.bot.add_view(ValidacionIncidenciasView(self))
        print("✅ Vistas Persistentes registradas (Tickets y Validación).")

    async def sitio_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        try: return [app_commands.Choice(name=r, value=r) for r in loc_manager.buscar(current)]
        except: return []

    @app_commands.command(name="reporte", description="Reportar incidencia o mantenimiento preventivo")
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
            
            # 🆕 Creamos la vista y le pasamos el objeto foto
            view = SeleccionMotivoView(sitio, foto.url, self)
            view.archivo_foto = foto  # Guardamos el objeto en la vista
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except: 
            await interaction.followup.send("❌ Error al iniciar el reporte.", ephemeral=True)

    async def crear_ticket_final(self, interaction, datos):
        try:
            # 🆕 NUEVA LÓGICA DE DRIVE
            # Si en los datos viene el objeto 'archivo_foto' (el attachment de Discord)
            archivo = datos.get('archivo_foto')
            ticket_id_temp = f"TEMP-{random.randint(100,999)}"  # ID temporal para el nombre del archivo
            
            link_drive = datos.get('foto_url')  # Por defecto la de Discord
            
            if archivo:
                await interaction.edit_original_response(content="☁️ Subiendo evidencia a Google Drive...")
                link_drive = await drive_service.subir_imagen_ticket(archivo, ticket_id_temp)
            # ------------------------------

            depto = datos.get('depto', '')
            sla_val = "4" if depto in [get_conf('DEPTO_SOPORTE', 'X'), get_conf('DEPTO_PAUTA', 'Y')] else "24"
            
            datos_db = {
                "tipo_registro": datos.get('tipo_registro', 'Incidencia'),
                "Sitio": datos.get('sitio', ''),
                "Unidad_de_negocio": datos.get('unidad', ''),
                "Departamento_Reporta": datos.get('depto', ''),
                "Motivo_Capturado": datos.get('motivo_capturado', ''),
                "Detalles_Extra": datos.get('detalles_extra', ''),
                "Usuario_Reporta": datos.get('usuario', ''),
                "Usuario_ID": str(datos.get('usuario_id', '')),
                "Foto_URL": datos.get('foto_url', ''),  # URL de Discord (rápida)
                "link_testigo_drive": link_drive,       # 🆕 URL de Drive (permanente)
                "Estatus": "Abierto",
                "SLA_Horas": sla_val
            }
            
            # nuevo_id = await db.crear_ticket(datos_db)
            nuevo_id = f"TICKET-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"  # Sustituir por db real
            
            if nuevo_id:
                # Actualizamos el nombre del archivo en Drive si quieres que coincida con el ID final
                # (Opcional, requiere una función de 'rename' en drive_service)
                
                await interaction.followup.send(
                    f"✅ **TICKET CREADO: {nuevo_id}**\n📂 Respaldo en Drive: [Abrir]({link_drive})", 
                    ephemeral=True
                )
                datos['ticket_id'] = nuevo_id
                datos['foto_url'] = link_drive  # Usamos la de Drive para el Hilo
                await self.crear_hilo_inicial(nuevo_id, datos)
            else:
                await interaction.followup.send("❌ Error guardando en BD.", ephemeral=True)
        except Exception as e:
            print(f"Error crear ticket: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    async def crear_hilo_inicial(self, ticket_id, datos):
        try:
            canal_general = self.bot.get_channel(CANAL_GENERAL_ID)
            if not canal_general: return
            
            color = 0xF1C40F if datos.get('tipo_registro') == "Mantenimiento Preventivo" else COLOR_ALERTA
            tipo_texto = "🛠️ Mantenimiento" if datos.get('tipo_registro') == "Mantenimiento Preventivo" else "🚨 Incidencia"

            embed = discord.Embed(title=f"{tipo_texto}: {datos['unidad']}", color=color)
            embed.add_field(name="🆔 Ticket", value=f"`{ticket_id}`", inline=True)
            embed.add_field(name="⚠️ Motivo", value=datos.get('motivo_capturado', ''), inline=True)
            embed.add_field(name="👷 Depto", value=datos['depto'], inline=True)
            embed.add_field(name="📍 Sitio", value=datos['sitio'], inline=False)
            
            # 🆕 Mostrar link de Drive si es diferente
            if datos.get('foto_url') and 'drive.google.com' in datos.get('foto_url', ''):
                embed.add_field(name="📂 Respaldo Drive", value=f"[Abrir imagen]({datos['foto_url']})", inline=False)
            
            if datos.get('detalles_extra'): 
                embed.add_field(name="📝 Descripción", value=datos['detalles_extra'], inline=False)
            embed.add_field(name="👤 Reportó", value=datos['usuario'], inline=True)
            
            if datos.get('foto_url') and 'drive.google.com' not in datos.get('foto_url', ''):
                embed.set_image(url=datos['foto_url'])
            
            hilo = await canal_general.create_thread(
                name=f"🔴 {ticket_id} | {datos.get('motivo_capturado', '')[:30]}", 
                type=discord.ChannelType.public_thread
            )
            
            # Dentro del Hilo: Usamos la vista Global (Persistente)
            await hilo.send(embed=embed, view=AccionesTicketGlobalView(self))
            if 'usuario_id' in datos: 
                await hilo.send(f"<@{datos['usuario_id']}> ticket creado.")
            
            # Añadimos el enlace al hilo dentro del Embed que va al grupo, así no perdemos el link si reiniciamos
            await self.notificar_nuevo_responsable(ticket_id, datos, hilo_url=hilo.jump_url)
        except Exception as e:
            print(f"❌ Error creando hilo: {e}")

    async def notificar_nuevo_responsable(self, ticket_id, datos, nota_extra="", hilo_url=None):
        try:
            deptos = get_conf('DEPARTAMENTOS', {})
            config_depto = deptos.get(datos['depto'])
            if config_depto:
                canal = self.bot.get_channel(config_depto['canal_id'])
                if canal:
                    embed = discord.Embed(
                        title=f"🔔 Asignación: {ticket_id}", 
                        description=f"[🔗 Clic aquí para ir al Ticket]({hilo_url})", 
                        color=COLOR_EMBED
                    )
                    embed.add_field(name="Sitio", value=datos['sitio'])
                    
                    # 🆕 Mostrar link de Drive si existe
                    if datos.get('foto_url') and 'drive.google.com' in datos.get('foto_url', ''):
                        embed.add_field(name="📂 Evidencia", value=f"[Drive]({datos['foto_url']})", inline=False)
                    
                    if nota_extra: 
                        embed.add_field(name="Nota", value=nota_extra, inline=False)
                    
                    # Como es solo lectura/aviso, no necesita los botones completos
                    view_aviso = discord.ui.View()
                    view_aviso.add_item(discord.ui.Button(label="Ir al Hilo", style=discord.ButtonStyle.link, url=hilo_url))
                    
                    await canal.send(f"<@&{config_depto['rol_id']}>", embed=embed, view=view_aviso)
        except: pass

    async def notificar_rechazo(self, ticket_id, datos, embed_rechazo):
        """Avisa al grupo responsable que su solución fue rechazada"""
        try:
            deptos = get_conf('DEPARTAMENTOS', {})
            config_depto = deptos.get(datos.get('depto'))
            if config_depto:
                canal = self.bot.get_channel(config_depto['canal_id'])
                if canal:
                    # Enviar el regaño al canal del departamento
                    await canal.send(f"⚠️ <@&{config_depto['rol_id']}> **¡Atención!**", embed=embed_rechazo)
        except Exception as e:
            print(f"Error notificando rechazo: {e}")

    async def notificar_cierre_global(self, ticket_id, datos_ticket, datos_res):
        try:
            embed = discord.Embed(title=f"🏁 Resuelto: {ticket_id}", color=COLOR_EXITO)
            embed.add_field(name="Solución", value=datos_res['solucion_brindada'])
            embed.add_field(name="Cerrado por", value=datos_res['cerrado_por'])
            
            # 🆕 Mostrar link de Drive si existe
            if datos_res.get('link_testigo_drive_solucion'):
                embed.add_field(name="📂 Evidencia Drive", value=f"[Abrir]({datos_res['link_testigo_drive_solucion']})", inline=False)
            
            if datos_res.get('foto_solucion'): 
                embed.set_thumbnail(url=datos_res['foto_solucion'])
            
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
