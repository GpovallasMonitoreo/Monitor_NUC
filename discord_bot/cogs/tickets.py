import discord
from discord import app_commands
from discord.ext import commands
import datetime
import traceback
import asyncio

# ==============================================================================
# 🛠️ CONFIGURACIÓN SEGURA
# ==============================================================================
from config import settings

COLOR_EMBED = getattr(settings, 'COLOR_EMBED', 0x3498DB)
COLOR_EXITO = getattr(settings, 'COLOR_EXITO', 0x2ECC71)
COLOR_ALERTA = getattr(settings, 'COLOR_ALERTA', 0xE74C3C)
COLOR_REASIGNADO = getattr(settings, 'COLOR_REASIGNADO', 0x9B59B6)
CANAL_GENERAL_ID = getattr(settings, 'CANAL_GENERAL_ID', 0)

# ==============================================================================
# IMPORTACIONES INTERNAS
# ==============================================================================
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
            style=discord.TextStyle.short,
            required=True
        )
        self.detalles_equipo = discord.ui.TextInput(
            label="¿Qué se hizo al equipo?",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.materiales = discord.ui.TextInput(
            label="Materiales Utilizados",
            style=discord.TextStyle.short,
            required=False
        )
        self.preventiva = discord.ui.TextInput(
            label="Acción Preventiva",
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.id_tecnologia = discord.ui.TextInput(
            label="ID Tecnología / Código Equipo",
            style=discord.TextStyle.short,
            required=False
        )

        for item in [
            self.area_causante,
            self.detalles_equipo,
            self.materiales,
            self.preventiva,
            self.id_tecnologia
        ]:
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        self.view.datos_cierre = {
            "incidencia_causada_por": self.area_causante.value,
            "detalles_equipo": self.detalles_equipo.value,
            "materiales_utilizados": self.materiales.value,
            "accion_preventiva": self.preventiva.value,
            "id_tecnologia": self.id_tecnologia.value
        }
        await interaction.response.send_message(
            "📝 Datos guardados.\n📸 Envía la FOTO DEL TESTIGO (Solución) ahora.",
            ephemeral=True
        )
        await self.view.esperar_foto(interaction)

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

        opciones_cat = [
            discord.SelectOption(label=cat[:100], value=cat[:100])
            for cat in CATALOGO_SOPORTE.keys()
        ]

        self.sel_categoria = discord.ui.Select(
            placeholder="1️⃣ Selecciona Categoría Principal",
            options=opciones_cat[:25]
        )
        self.sel_categoria.callback = self.on_categoria_change
        self.add_item(self.sel_categoria)

    async def on_categoria_change(self, interaction: discord.Interaction):
        self.seleccion["categoria"] = self.sel_categoria.values[0]

        incidencias = list(CATALOGO_SOPORTE[self.seleccion["categoria"]].keys())
        opciones_inc = [discord.SelectOption(label=i[:100], value=i[:100]) for i in incidencias[:25]]

        self.clear_items()
        self.add_item(self.sel_categoria)

        self.sel_incidencia = discord.ui.Select(
            placeholder="2️⃣ Tipo de Incidencia",
            options=opciones_inc
        )
        self.sel_incidencia.callback = self.on_incidencia_change
        self.add_item(self.sel_incidencia)

        await interaction.response.edit_message(view=self)

    async def on_incidencia_change(self, interaction: discord.Interaction):
        self.seleccion["incidencia"] = self.sel_incidencia.values[0]

        causas = list(
            CATALOGO_SOPORTE[self.seleccion["categoria"]][self.seleccion["incidencia"]].keys()
        )
        opciones_causa = [discord.SelectOption(label=c[:100], value=c[:100]) for c in causas[:25]]

        self.clear_items()
        self.add_item(self.sel_categoria)
        self.add_item(self.sel_incidencia)

        self.sel_causa = discord.ui.Select(
            placeholder="3️⃣ Causa Raíz",
            options=opciones_causa
        )
        self.sel_causa.callback = self.on_causa_change
        self.add_item(self.sel_causa)

        await interaction.response.edit_message(view=self)

    async def on_causa_change(self, interaction: discord.Interaction):
        self.seleccion["causa"] = self.sel_causa.values[0]

        nodo = CATALOGO_SOPORTE[self.seleccion["categoria"]][self.seleccion["incidencia"]][self.seleccion["causa"]]
        soluciones = nodo.get("soluciones", []) if isinstance(nodo, dict) else nodo
        opciones_sol = [discord.SelectOption(label=s[:100], value=s[:100]) for s in soluciones[:25]]

        self.clear_items()
        self.add_item(self.sel_categoria)
        self.add_item(self.sel_incidencia)
        self.add_item(self.sel_causa)

        self.sel_solucion = discord.ui.Select(
            placeholder="4️⃣ Pasos de Solución",
            options=opciones_sol
        )
        self.sel_solucion.callback = self.on_solucion_change
        self.add_item(self.sel_solucion)

        await interaction.response.edit_message(view=self)

    async def on_solucion_change(self, interaction: discord.Interaction):
        self.seleccion["solucion"] = self.sel_solucion.values[0]
        await interaction.response.send_modal(DetallesCierreModal(self, interaction))

    async def esperar_foto(self, interaction: discord.Interaction):
        def check(m):
            return (
                m.author == interaction.user
                and m.channel == interaction.channel
                and len(m.attachments) > 0
            )

        try:
            mensaje_foto = await self.cog.bot.wait_for('message', check=check, timeout=120)
            self.seleccion["foto_solucion"] = mensaje_foto.attachments[0].url
            await self.finalizar_ticket(interaction)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Tiempo agotado.", ephemeral=True)

    async def finalizar_ticket(self, interaction: discord.Interaction):
        try:
            if self.mensaje_controles:
                await self.mensaje_controles.edit(view=None, content="🔒 Ticket Cerrado")
        except Exception:
            pass

        await db.actualizar_estatus(self.ticket_id, "Resuelto", {})

        embed = discord.Embed(title="✅ TICKET RESUELTO", color=COLOR_EXITO)
        embed.add_field(name="ID", value=self.ticket_id)

        if isinstance(interaction.channel, discord.Thread):
            await interaction.channel.send(embed=embed)
        else:
            await interaction.followup.send(embed=embed)

# ==============================================================================
# ⚙️ COMANDO PRINCIPAL
# ==============================================================================
class SistemaTickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reporte", description="Reportar incidencia")
    async def reporte(self, interaction: discord.Interaction, sitio: str, foto: discord.Attachment):
        if not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Debe ser una imagen.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="📋 Nuevo Reporte",
            description=f"📍 Sitio: {sitio}",
            color=COLOR_EMBED
        )
        embed.set_thumbnail(url=foto.url)

        await interaction.followup.send(embed=embed, ephemeral=True)

# ==============================================================================
# SETUP
# ==============================================================================
async def setup(bot):
    await bot.add_cog(SistemaTickets(bot))
