import discord
from discord import app_commands
from discord.ext import commands
import datetime
from core.database import db
from core.settings import *

class RutasBiobox(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="biobox", description="Ver progreso de ruta de un técnico")
    @app_commands.describe(tecnico="Nombre del técnico a consultar")
    async def biobox(self, interaction: discord.Interaction, tecnico: str):
        # Solo permitir en canales de Biobox
        if "biobox" not in interaction.channel.name.lower() and interaction.channel.id != CANAL_GENERAL_ID:
            return await interaction.response.send_message("❌ Usa este comando en el canal de Biobox.", ephemeral=True)

        await interaction.response.defer()

        # Llamamos a la función de database.py que ya creamos
        visitados, pendientes = await db.obtener_recorrido_biobox(tecnico)

        if visitados is None:
            return await interaction.followup.send(f"❓ No encontré una ruta asignada para **{tecnico}**.")

        total = len(visitados) + len(pendientes)
        progreso = (len(visitados) / total) * 100 if total > 0 else 0

        embed = discord.Embed(
            title=f"🗺️ Ruta Biobox: {tecnico.upper()}",
            description=f"**Progreso de hoy:** {len(visitados)} / {total} sitios",
            color=COLOR_EXITO if progreso == 100 else 0xF1C40F
        )

        # Barra de progreso visual
        bloques = int(progreso / 10)
        barra = "🟩" * bloques + "⬜" * (10 - bloques)
        embed.add_field(name="Avance", value=f"{barra} `{progreso:.1f}%`", inline=False)

        # Listas de sitios
        txt_visitados = "\n".join([f"✅ {s}" for s in visitados]) if visitados else "Ninguno aún"
        txt_pendientes = "\n".join([f"🔴 {s}" for s in pendientes[:15]]) # Top 15 pendientes
        
        embed.add_field(name="Visitados", value=txt_visitados, inline=True)
        embed.add_field(name="Pendientes", value=txt_pendientes, inline=True)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(RutasBiobox(bot))
