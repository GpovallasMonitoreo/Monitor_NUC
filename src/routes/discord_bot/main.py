"""
Main entry point for SyncOps Discord Bot
"""

import discord
from discord.ext import commands
import os
import asyncio
import traceback
import sys
from dotenv import load_dotenv

# Añadir ruta para imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(src_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Importar keep_alive para Render
try:
    from discord_bot.keep_alive import keep_alive
    keep_alive()
    print("🌐 Keep-alive activado para entorno Render")
except ImportError as e:
    print(f"⚠️ No se pudo importar keep_alive: {e}")

# Cargar variables de entorno
load_dotenv()

# Configuración del bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    """Evento cuando el bot se conecta exitosamente"""
    print("=" * 50)
    print(f"✅ BOT CONECTADO EXITOSAMENTE")
    print(f"🤖 Nombre: {bot.user}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"🌐 Servidores: {len(bot.guilds)}")
    print("=" * 50)
    
    # Sincronizar comandos de barra
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos sincronizados.")
        
        # Mostrar comandos disponibles
        commands_list = await bot.tree.fetch_commands()
        if commands_list:
            print("📝 Comandos slash disponibles:")
            for cmd in commands_list:
                print(f"   - /{cmd.name}: {cmd.description}")
    except Exception as e:
        print(f"❌ Error sincronizando comandos: {e}")
        traceback.print_exc()

@bot.event
async def on_guild_join(guild):
    """Evento cuando el bot es añadido a un servidor"""
    print(f"🎉 Bot añadido al servidor: {guild.name} (ID: {guild.id})")
    
    # Buscar canal de texto para enviar mensaje de bienvenida
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            embed = discord.Embed(
                title="🤖 SyncOps Bot Conectado",
                description="Gracias por añadirme a tu servidor!",
                color=0x3498db
            )
            embed.add_field(
                name="Comandos Disponibles",
                value="• `/reporte` - Crear un nuevo ticket\n• `/analisis` - Ver estadísticas",
                inline=False
            )
            embed.add_field(
                name="Soporte",
                value="Para configurar el bot, contacta al administrador.",
                inline=False
            )
            embed.set_footer(text="SyncOps Sistema de Tickets")
            
            try:
                await channel.send(embed=embed)
                break
            except:
                continue

async def cargar_cogs():
    """Cargar todos los módulos (cogs) del bot"""
    cogs_to_load = [
        "discord_bot.cogs.tickets",
        "discord_bot.cogs.analisis"
    ]
    
    print("📦 Cargando módulos...")
    
    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            print(f"   ✅ {cog}")
        except Exception as e:
            print(f"   ❌ {cog}: {e}")
            traceback.print_exc()

@bot.event
async def on_command_error(ctx, error):
    """Manejo de errores de comandos"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignorar comandos no encontrados
    
    print(f"⚠️ Error en comando {ctx.command}: {error}")
    
    embed = discord.Embed(
        title="❌ Error",
        description=f"Ocurrió un error: ```{str(error)[:100]}```",
        color=0xe74c3c
    )
    
    try:
        await ctx.send(embed=embed)
    except:
        pass

async def main():
    """Función principal de arranque del bot"""
    token = os.getenv("DISCORD_TOKEN")
    
    if not token:
        print("❌ ERROR: No se encontró DISCORD_TOKEN en las variables de entorno")
        print("💡 Configura DISCORD_TOKEN en Render.com → Environment")
        return
    
    print("🚀 Iniciando SyncOps Discord Bot...")
    print(f"📁 Directorio: {os.getcwd()}")
    print(f"🔧 Entorno: {'Render' if os.getenv('RENDER') else 'Local'}")
    print(f"🔑 Token: {'Presente' if token else 'Ausente'}")
    
    # Verificar archivos esenciales
    essential_files = [
        ('data/sitios.csv', 'src/discord_bot/data/sitios.csv'),
        ('cogs/tickets.py', 'src/discord_bot/cogs/tickets.py'),
        ('config/settings.py', 'src/discord_bot/config/settings.py')
    ]
    
    print("🔍 Verificando archivos esenciales...")
    for file_name, file_path in essential_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_name}")
        else:
            print(f"   ❌ {file_name} (no encontrado en {file_path})")
    
    async with bot:
        try:
            await cargar_cogs()
            print("✅ Todos los módulos cargados")
            print("🔗 Conectando a Discord...")
            await bot.start(token)
        except discord.LoginFailure:
            print("❌ ERROR: Token de Discord inválido o expirado")
        except KeyboardInterrupt:
            print("\n👋 Bot detenido manualmente")
        except Exception as e:
            print(f"💥 Error crítico: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Programa terminado")
    except Exception as e:
        print(f"💥 Error en ejecución principal: {e}")
