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
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Importar keep_alive solo si estamos en Render
if os.environ.get('RENDER', False) or os.environ.get('PORT'):
    from discord_bot.keep_alive import keep_alive
    keep_alive()
    print("🌐 Modo Render detectado - Servidor web activado")

# Cargar entorno
load_dotenv()

# Configuración
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    print(f"🆔 ID del bot: {bot.user.id}")
    print(f"🌐 Guild ID: {os.getenv('GUILD_ID', 'No configurado')}")
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos sincronizados.")
        
        # Mostrar comandos disponibles
        commands_list = await bot.tree.fetch_commands()
        if commands_list:
            print("📝 Comandos disponibles:")
            for cmd in commands_list:
                print(f"   - /{cmd.name}: {cmd.description}")
    except Exception as e:
        print(f"❌ Error sync: {e}")
        traceback.print_exc()

async def cargar_cogs():
    """Carga todos los cogs del sistema"""
    cogs_to_load = ["discord_bot.cogs.tickets", "discord_bot.cogs.analisis"]
    
    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            print(f"✅ Cog '{cog}' cargado correctamente.")
        except Exception as e:
            print(f"❌ Error cargando '{cog}': {e}")
            traceback.print_exc()

@bot.event
async def on_command_error(ctx, error):
    """Manejo de errores de comandos"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Comando no encontrado. Usa `/reporte` para crear un ticket.")
    else:
        print(f"⚠️ Error no manejado: {error}")
        await ctx.send(f"⚠️ Ocurrió un error: {str(error)[:100]}")

async def main():
    """Función principal de arranque"""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ ERROR: No hay DISCORD_TOKEN en las variables de entorno")
        print("💡 Asegúrate de configurar DISCORD_TOKEN en Render.com")
        return

    print("🚀 Iniciando SyncOps Bot...")
    print(f"📁 Directorio actual: {os.getcwd()}")
    print(f"📁 Ruta del bot: {current_dir}")
    print(f"🐍 Python version: {os.sys.version}")
    
    # Verificar archivos importantes
    required_files = [
        'src/discord_bot/data/sitios.csv',
        'src/discord_bot/cogs/tickets.py',
        'src/discord_bot/config/settings.py'
    ]
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} encontrado")
        else:
            print(f"⚠️ {file} no encontrado")

    async with bot:
        await cargar_cogs()
        try:
            print(f"🔑 Token length: {len(token)} caracteres")
            await bot.start(token)
        except discord.LoginFailure:
            print("❌ ERROR: Token de Discord inválido")
        except Exception as e:
            print(f"❌ Error crítico al iniciar el bot: {e}")
            traceback.print_exc()

# Punto de entrada principal
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot detenido por el usuario")
    except Exception as e:
        print(f"💥 Error fatal: {e}")
        traceback.print_exc()
