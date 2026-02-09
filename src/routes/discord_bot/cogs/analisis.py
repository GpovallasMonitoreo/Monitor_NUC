"""
Cog para análisis y estadísticas de tickets
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord_bot.core.database import db
from discord_bot.config import settings
import pandas as pd
import io

class AnalisisTickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ Cog AnalisisTickets inicializado")

    async def obtener_datos_analisis(self, filtro_sitio=None):
        """Obtener datos de tickets para análisis"""
        # Esta función necesita ser implementada en database.py
        # Por ahora retornamos datos de ejemplo
        return []

    @app_commands.command(name="analisis", description="Obtener estadísticas de tickets")
    @app_commands.describe(sitio="Opcional: Filtrar por un sitio específico")
    async def analisis(self, interaction: discord.Interaction, sitio: str = None):
        """Comando para mostrar análisis de tickets"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 1. Obtener Datos
            tickets = await self.obtener_datos_analisis(filtro_sitio=sitio)
            
            if not tickets:
                await interaction.followup.send(
                    "📭 No hay datos para mostrar en este momento.", 
                    ephemeral=True
                )
                return

            # 2. Procesar con Pandas
            df = pd.DataFrame(tickets)
            
            total = len(df)
            abiertos = len(df[df['Estatus'] == 'Abierto'])
            resueltos = len(df[df['Estatus'] == 'Resuelto'])
            en_proceso = len(df[df['Estatus'] == 'En Proceso'])
            reasignados = len(df[df['Estatus'] == 'Reasignado'])
            
            # Top Fallas
            if 'Motivo del reporte' in df.columns:
                top_fallas = df['Motivo del reporte'].value_counts().head(5)
                top_fallas_str = "\n".join([f"{i+1}. {motivo}: {count}" for i, (motivo, count) in enumerate(top_fallas.items())])
            else:
                top_fallas_str = "No hay datos disponibles"

            # Top Sitios con más tickets
            if 'Sitio' in df.columns:
                top_sitios = df['Sitio'].value_counts().head(5)
                top_sitios_str = "\n".join([f"{i+1}. {sitio}: {count}" for i, (sitio, count) in enumerate(top_sitios.items())])
            else:
                top_sitios_str = "No hay datos disponibles"

            # 3. Crear Reporte Visual
            embed = discord.Embed(
                title="📊 Análisis de Operaciones - SyncOps",
                description="Estadísticas generales del sistema de tickets",
                color=settings.COLOR_ANALISIS,
                timestamp=discord.utils.utcnow()
            )
            
            if sitio:
                embed.description = f"**Datos filtrados para:** {sitio}"
            
            # Estadísticas principales
            embed.add_field(
                name="📈 Estadísticas Principales", 
                value=(
                    f"**Total Tickets:** {total}\n"
                    f"**🔴 Abiertos:** {abiertos}\n"
                    f"**🟡 En Proceso:** {en_proceso}\n"
                    f"**🟢 Resueltos:** {resueltos}\n"
                    f"**🔄 Reasignados:** {reasignados}\n"
                    f"**📊 Tasa de Resolución:** {((resueltos/total)*100):.1f}%"
                ), 
                inline=True
            )
            
            # Top Incidencias
            embed.add_field(
                name="🔥 Top 5 Incidencias", 
                value=f"```{top_fallas_str}```", 
                inline=False
            )
            
            # Top Sitios
            embed.add_field(
                name="📍 Top 5 Sitios", 
                value=f"```{top_sitios_str}```", 
                inline=False
            )
            
            # Información adicional
            if 'Departamento_Reporta' in df.columns:
                deptos = df['Departamento_Reporta'].value_counts()
                depto_principal = deptos.index[0] if len(deptos) > 0 else "N/A"
                embed.add_field(
                    name="🏢 Departamento más activo", 
                    value=f"**{depto_principal}** ({deptos.iloc[0] if len(deptos) > 0 else 0} tickets)",
                    inline=True
                )
            
            embed.set_footer(text="SyncOps Analytics • Actualizado")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Error en comando /analisis: {e}")
            await interaction.followup.send(
                "❌ Error al generar el análisis. Intenta nuevamente.", 
                ephemeral=True
            )

    @app_commands.command(name="estadisticas", description="Estadísticas detalladas (archivo CSV)")
    @app_commands.describe(dias="Número de días hacia atrás para analizar (opcional)")
    async def estadisticas(self, interaction: discord.Interaction, dias: int = 30):
        """Comando para generar estadísticas detalladas en CSV"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Obtener datos (esto es un ejemplo, ajusta según tu implementación)
            tickets = await self.obtener_datos_analisis()
            
            if not tickets:
                await interaction.followup.send(
                    "📭 No hay datos para generar estadísticas.", 
                    ephemeral=True
                )
                return
            
            df = pd.DataFrame(tickets)
            
            # Crear CSV en memoria
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8')
            output.seek(0)
            
            # Crear archivo para Discord
            csv_file = discord.File(
                io.BytesIO(output.getvalue().encode('utf-8')), 
                filename=f"estadisticas_tickets_{discord.utils.utcnow().strftime('%Y%m%d')}.csv"
            )
            
            embed = discord.Embed(
                title="📊 Estadísticas Exportadas",
                description=f"Se han exportado {len(df)} tickets.",
                color=settings.COLOR_ANALISIS
            )
            
            embed.add_field(name="📁 Archivo", value="CSV con todos los datos", inline=True)
            embed.add_field(name="📅 Período", value=f"Últimos {dias} días", inline=True)
            embed.add_field(name="📈 Registros", value=str(len(df)), inline=True)
            
            await interaction.followup.send(embed=embed, file=csv_file, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Error en comando /estadisticas: {e}")
            await interaction.followup.send(
                "❌ Error al generar estadísticas. Intenta nuevamente.", 
                ephemeral=True
            )

async def setup(bot):
    """Setup del cog"""
    try:
        await bot.add_cog(AnalisisTickets(bot))
        print("✅ Cog AnalisisTickets agregado al bot")
    except Exception as e:
        print(f"❌ Error agregando cog AnalisisTickets: {e}")
