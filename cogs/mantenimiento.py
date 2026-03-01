import discord
from discord import app_commands
from discord.ext import commands
import datetime
from core.database import db
from core.settings import *
from src.services.drive_service import DriveService
from utils.utils import detectar_unidad

drive_service = DriveService()

class MantenimientoModal(discord.ui.Modal, title='Reporte de Mantenimiento Preventivo'):
    sitio = discord.ui.TextInput(label='ID del Sitio (Ej. MX_CM_BB_001)', required=True)
    actividades = discord.ui.TextInput(
        label='Actividades Realizadas',
        style=discord.TextStyle.paragraph,
        placeholder='Limpieza de filtros, revisión de NUC, limpieza de cristales...',
        required=True
    )

    def __init__(self, adjunto: discord.Attachment):
        super().__init__()
        self.adjunto = adjunto

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        id_mant = f"MANT-{datetime.datetime.now().strftime('%y%m%d%H%M')}"
        unidad = detectar_unidad(self.sitio.value)
        
        # 1. Subir a Drive
        link_drive = await drive_service.subir_imagen_ticket(self.adjunto, id_mant, tipo="preventivo")

        # 2. Lógica de guardado doble
        datos_comunes = {
            "sitio_id": self.sitio.value.upper(),
            "tecnico": interaction.user.display_name,
            "unidad_negocio": unidad,
            "fecha": datetime.datetime.now().strftime("%Y-%m-%d"),
            "hora": datetime.datetime.now().strftime("%H:%M:%S"),
            "actividades": self.actividades.value,
            "link_evidencia_drive": link_drive
        }

        if unidad == "BIOBOX":
            # Si es Biobox, alimentamos la tabla de tickets_biobox marcándolo como preventivo
            await db.supabase.table('tickets_biobox').insert({
                "ticket_id": id_mant,
                "tipo_registro": "Mantenimiento Preventivo",
                "sitio_id": datos_comunes["sitio_id"],
                "motivo_incidencia": "Mantenimiento Preventivo",
                "solucion_brindada": self.actividades.value,
                "link_testigo_drive": link_drive,
                "estatus": "Cerrado",
                "medio": "BioBox"
            }).execute()
        
        # En ambos casos (Biobox o Vía Verde) guardamos en la tabla general de Mantenimientos
        await db.supabase.table('mantenimientos_op_digital').insert(datos_comunes).execute()

        # 3. Respuesta visual
        embed = discord.Embed(title="✅ Mantenimiento Registrado", color=COLOR_EXITO)
        embed.add_field(name="ID", value=id_mant)
        embed.add_field(name="Sitio", value=self.sitio.value.upper())
        embed.add_field(name="Evidencia", value=f"[Ver en Drive]({link_drive})")
        
        await interaction.followup.send(embed=embed)

class MantenimientoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mantenimiento", description="Registra un mantenimiento preventivo (Biobox o Vía Verde)")
    async def mantenimiento(self, interaction: discord.Interaction, foto: discord.Attachment):
        if not foto.content_type.startswith("image/"):
            return await interaction.response.send_message("❌ Sube una imagen válida.", ephemeral=True)
        
        await interaction.response.send_modal(MantenimientoModal(adjunto=foto))

async def setup(bot):
    await bot.add_cog(MantenimientoCog(bot))
