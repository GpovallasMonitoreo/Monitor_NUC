import discord
from discord import app_commands
from discord.ext import commands
import io
import pandas as pd  # Necesitas: pip install pandas

# Imports absolutos seguros (compatibles local y Render)
try:
    from discord_bot.core.database import db
    from discord_bot.config import settings
except ImportError:
    from core.database import db
    from config import settings


class AnalisisTickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="analisis", description="Obtener estadísticas de tickets")
    @app_commands.describe(sitio="Opcional: Filtrar por un sitio específico")
    async def analisis(self, interaction: discord.Interaction, sitio: str = None):
        await interaction.response.defer(ephemeral=True)
        
        # 1. Obtener Datos (con protección de errores)
        try:
            tickets = await db.obtener_datos_analisis(filtro_sitio=sitio)
        except Exception:
            await interaction.followup.send(
                "❌ Error consultando la base de datos.",
                ephemeral=True
            )
            return
        
        if not tickets:
            await interaction.followup.send("📭 No hay datos para mostrar.", ephemeral=True)
            return

        # 2. Procesar con Pandas
        df = pd.DataFrame(tickets)
        
        total = len(df)
        abiertos = len(df[df['Estatus'] == 'Abierto'])
        resueltos = len(df[df['Estatus'] == 'Resuelto'])
        
        # Top Fallas
        if 'Motivo del reporte' in df.columns:
            top_fallas = df['Motivo del reporte'].value_counts().head(3).to_string()
        else:
            top_fallas = "N/A"

        # 3. Crear Reporte Visual
        embed = discord.Embed(title="📊 Análisis de Operaciones", color=settings.COLOR_ANALISIS)
        if sitio:
            embed.description = f"Datos filtrados para: **{sitio}**"
        
        embed.add_field(name="Total Tickets", value=str(total), inline=True)
        embed.add_field(name="🔴 Abiertos", value=str(abiertos), inline=True)
        embed.add_field(name="🟢 Resueltos", value=str(resueltos), inline=True)
        embed.add_field(name="🔥 Top Incidencias", value=f"```{top_fallas}```", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AnalisisTickets(bot))
