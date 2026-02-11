import discord
from discord.ext import commands
import os
import asyncio
import traceback
import sys
from dotenv import load_dotenv

# ==============================================================================
# 🛠️ PARCHE PARA PYINSTALLER
# ==============================================================================
# Solo importamos supabase para forzar a PyInstaller a incluir la librería en el .exe
# No necesitamos usarla aquí, solo que el compilador vea el "import".
try:
    import supabase
    from supabase import create_client, Client
except ImportError:
    print("⚠️ Advertencia: La librería 'supabase' no está instalada en este entorno.")
# ==============================================================================

# ==========================================
# 📍 CONFIGURACIÓN DE RUTAS Y ENTORNO
# ==========================================
# Detectar si estamos ejecutando como .exe o como script .py
if getattr(sys, 'frozen', False):
    # Si es .exe, la ruta base es la carpeta del ejecutable
    base_path = os.path.dirname(sys.executable)
else:
    # Si es script, la ruta base es donde está el archivo
    base_path = os.path.dirname(os.path.abspath(__file__))

# Cargar .env buscando explícitamente en la ruta correcta
env_path = os.path.join(base_path, ".env")
load_dotenv(env_path)

# ==========================================
# 🤖 CONFIGURACIÓN DEL BOT
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print("="*50)
    print(f"✅ BOT CONECTADO: {bot.user.name}")
    print(f"🆔 ID: {bot.user.id}")
    print("="*50)
    
    # Sincronizar comandos (slash commands)
    try:
        print("⏳ Sincronizando comandos con Discord...")
        synced = await bot.tree.sync()
        print(f"✅ Sincronización exitosa: {len(synced)} comandos activos.")
        for cmd in synced:
            print(f"   - /{cmd.name}")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")

async def cargar_cogs():
    """Carga las extensiones (Cogs)"""
    print("📂 Cargando módulos...")
    try:
        # Aseguramos que python pueda ver la carpeta actual para imports relativos
        if base_path not in sys.path:
            sys.path.append(base_path)
        
        # Intentamos cargar el cog de tickets
        # PyInstaller no ve 'cogs' automáticamente, por eso necesitamos la carpeta física al lado
        await bot.load_extension("cogs.tickets")
        print("   ✅ Cog 'cogs.tickets' cargado correctamente.")
        
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO CARGANDO COGS:")
        print(f"   No se pudo cargar 'cogs.tickets'.")
        print(f"   Posible causa: Falta la carpeta 'cogs' o 'core' al lado del .exe")
        print(f"   Detalle del error: {e}")
        print("-" * 30)
        traceback.print_exc()
        print("-" * 30)

async def main():
    token = os.getenv("DISCORD_TOKEN")
    
    if not token:
        print("\n❌ ERROR DE CONFIGURACIÓN:")
        print("   No se encontró 'DISCORD_TOKEN'.")
        print(f"   1. Asegúrate de que el archivo .env existe en: {base_path}")
        print("   2. Asegúrate de que tenga el formato DISCORD_TOKEN=tu_token")
        input("\n⛔ Presiona ENTER para salir...")
        return

    async with bot:
        await cargar_cogs()
        try:
            print(f"🚀 Iniciando conexión...")
            await bot.start(token)
        except Exception as e:
            print(f"\n❌ Error de conexión con Discord: {e}")

if __name__ == "__main__":
    try:
        # Limpiar consola (estético)
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"🔵 INICIANDO SYNCOPS MONITOR (MODO CONSOLA)")
        print(f"📂 Directorio Base: {base_path}")
        
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot detenido manualmente.")
    except Exception as e:
        print(f"\n❌ Error fatal no manejado: {e}")
        traceback.print_exc()
    finally:
        # Mantiene la ventana abierta si hay error o cierre
        input("\n⛔ Presiona ENTER para cerrar la ventana...")
