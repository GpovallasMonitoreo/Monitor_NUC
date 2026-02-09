"""
SyncOps Discord Bot - Main Entry Point
Versión optimizada para Render (Web Service con health checks)
"""

import discord
from discord.ext import commands
import os
import asyncio
import traceback
import sys
import logging
from datetime import datetime
import threading
from aiohttp import web

# ==============================================================================
# CONFIGURACIÓN DE LOGGING
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURACIÓN DE RUTAS
# ==============================================================================

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(src_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("=" * 60)
print("🤖 SYCEOPS DISCORD BOT - INICIALIZANDO")
print("=" * 60)
print(f"📁 Directorio: {current_dir}")
print(f"🐍 Python: {sys.version}")
print(f"📅 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ==============================================================================
# SERVIDOR WEB PARA HEALTH CHECKS (RENDER WEB SERVICE)
# ==============================================================================

class HealthServer:
    """Servidor web minimalista para health checks de Render"""
    
    def __init__(self, host='0.0.0.0', port=10000):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.setup_routes()
        self.runner = None
        self.site = None
        
    def setup_routes(self):
        """Configurar rutas del servidor web"""
        self.app.add_routes([
            web.get('/', self.handle_root),
            web.get('/health', self.handle_health),
            web.get('/ping', self.handle_ping),
            web.get('/info', self.handle_info),
            web.get('/status', self.handle_status)
        ])
    
    async def handle_root(self, request):
        """Manejar ruta raíz"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>🤖 SyncOps Discord Bot</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
                .status { padding: 15px; border-radius: 8px; margin: 20px 0; }
                .online { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
                .endpoints { background-color: #f8f9fa; padding: 15px; border-radius: 8px; }
                .endpoint { margin: 5px 0; font-family: monospace; }
            </style>
        </head>
        <body>
            <h1>🤖 SyncOps Discord Bot</h1>
            <div class="status online">
                <strong>✅ Estado:</strong> Bot activo y funcionando
            </div>
            <p>Este es un bot de Discord para gestión de tickets de soporte.</p>
            
            <h3>📊 Endpoints disponibles:</h3>
            <div class="endpoints">
                <div class="endpoint"><strong>GET</strong> /health → Health check para Render</div>
                <div class="endpoint"><strong>GET</strong> /ping → Respuesta "pong"</div>
                <div class="endpoint"><strong>GET</strong> /status → Estado del bot</div>
                <div class="endpoint"><strong>GET</strong> /info → Información del sistema</div>
            </div>
            
            <h3>🔧 Comandos de Discord:</h3>
            <ul>
                <li><code>/reporte</code> → Crear nuevo ticket</li>
                <li><code>/analisis</code> → Ver estadísticas</li>
                <li><code>/ayuda</code> → Mostrar ayuda</li>
            </ul>
            
            <p><em>Sistema operativo desde: {time}</em></p>
        </body>
        </html>
        """.format(time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return web.Response(text=html, content_type='text/html')
    
    async def handle_health(self, request):
        """Endpoint de health check para Render"""
        return web.Response(
            text="✅ OK - SyncOps Bot\n",
            status=200,
            headers={'Content-Type': 'text/plain; charset=utf-8'}
        )
    
    async def handle_ping(self, request):
        """Endpoint de ping"""
        return web.Response(
            text="🏓 Pong!\n",
            headers={'Content-Type': 'text/plain; charset=utf-8'}
        )
    
    async def handle_info(self, request):
        """Endpoint de información del sistema"""
        import platform
        info = f"""
🤖 SyncOps Discord Bot - Información del Sistema
===============================================
• Estado: Activo
• Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• Python: {platform.python_version()}
• Plataforma: {platform.platform()}
• Directorio: {os.getcwd()}
• Entorno: {'Render' if os.getenv('RENDER') else 'Local'}
• Puerto: {self.port}
• PID: {os.getpid()}
===============================================
        """
        return web.Response(
            text=info,
            headers={'Content-Type': 'text/plain; charset=utf-8'}
        )
    
    async def handle_status(self, request):
        """Endpoint de estado del bot"""
        bot_status = "❓ Desconocido"
        if 'bot' in globals() and bot and hasattr(bot, 'is_ready'):
            bot_status = "✅ Conectado" if bot.is_ready() else "🔄 Conectando..."
        
        status_data = {
            "bot": bot_status,
            "webserver": "✅ Activo",
            "timestamp": datetime.now().isoformat(),
            "service": "syncops-discord-bot",
            "environment": os.getenv('RENDER', 'development')
        }
        
        import json
        return web.Response(
            text=json.dumps(status_data, indent=2),
            content_type='application/json'
        )
    
    async def start(self):
        """Iniciar servidor web"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        print(f"🌍 Servidor web iniciado en http://{self.host}:{self.port}")
        print(f"🔗 Health check: http://{self.host}:{self.port}/health")
    
    async def stop(self):
        """Detener servidor web"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        print("🌍 Servidor web detenido")

# ==============================================================================
# INICIALIZACIÓN DEL BOT DE DISCORD
# ==============================================================================

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    
    env_paths = [
        os.path.join(project_root, '.env'),
        os.path.join(current_dir, '.env'),
        '.env'
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print(f"✅ Variables cargadas desde: {env_path}")
            break
    else:
        print("ℹ️  No se encontró archivo .env, usando variables del sistema")
        
except ImportError:
    print("⚠️  python-dotenv no instalado, usando variables de entorno del sistema")

# Verificar token de Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    print("❌ ERROR CRÍTICO: DISCORD_TOKEN no encontrado")
    print("💡 Configura DISCORD_TOKEN en:")
    print("   - Render.com: Environment Variables")
    print("   - Local: Archivo .env")
    sys.exit(1)
else:
    token_preview = DISCORD_TOKEN[:10] + "..." + DISCORD_TOKEN[-5:] if len(DISCORD_TOKEN) > 15 else "***"
    print(f"✅ Discord Token: Presente ({len(DISCORD_TOKEN)} caracteres)")
    print(f"🔐 Token preview: {token_preview}")

# Configuración del bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Crear bot
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
    case_insensitive=True
)

# ==============================================================================
# EVENTOS DEL BOT
# ==============================================================================

@bot.event
async def on_ready():
    """Evento cuando el bot se conecta exitosamente"""
    print("=" * 60)
    print(f"✅ BOT CONECTADO EXITOSAMENTE")
    print(f"🤖 Nombre: {bot.user}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"📅 Hora: {datetime.now().strftime('%H:%M:%S')}")
    print(f"🌐 Servidores: {len(bot.guilds)}")
    print("=" * 60)
    
    # Mostrar información de servidores
    for guild in bot.guilds:
        print(f"   📍 {guild.name} (ID: {guild.id})")
    
    # Sincronizar comandos slash
    try:
        print("🔄 Sincronizando comandos slash...")
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos sincronizados")
        
        # Mostrar comandos disponibles
        commands_list = await bot.tree.fetch_commands()
        if commands_list:
            print("📝 Comandos disponibles:")
            for cmd in commands_list:
                print(f"   - /{cmd.name}: {cmd.description}")
                
    except Exception as e:
        print(f"❌ Error sincronizando comandos: {e}")
        traceback.print_exc()
    
    # Cambiar estado del bot
    try:
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="tickets | /reporte"
            )
        )
        print("🎮 Estado del bot actualizado")
    except Exception as e:
        print(f"⚠️  Error actualizando estado: {e}")
    
    print("✅ Bot listo y operativo")

@bot.event
async def on_guild_join(guild):
    """Evento cuando el bot es añadido a un servidor"""
    print(f"🎉 Bot añadido al servidor: {guild.name} (ID: {guild.id})")
    
    # Buscar canal para enviar mensaje de bienvenida
    welcome_channel = None
    
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            welcome_channel = channel
            break
    
    if welcome_channel:
        embed = discord.Embed(
            title="🤖 SyncOps Bot Conectado",
            description="¡Gracias por añadirme a tu servidor!",
            color=0x3498db,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="Comandos Disponibles",
            value="• `/reporte` - Crear un nuevo ticket\n• `/analisis` - Ver estadísticas\n• `/ayuda` - Mostrar ayuda",
            inline=False
        )
        
        embed.add_field(
            name="Configuración",
            value="Para configurar canales y permisos, contacta al administrador.",
            inline=False
        )
        
        embed.set_footer(text="SyncOps Sistema de Tickets")
        
        try:
            await welcome_channel.send(embed=embed)
        except Exception as e:
            print(f"⚠️  No se pudo enviar mensaje de bienvenida: {e}")

@bot.event
async def on_command_error(ctx, error):
    """Manejo de errores de comandos"""
    if isinstance(error, commands.CommandNotFound):
        return
    
    logger.error(f"Error en comando {ctx.command}: {error}")
    
    # Crear embed de error
    embed = discord.Embed(
        title="❌ Error",
        color=0xe74c3c,
        timestamp=datetime.now()
    )
    
    if isinstance(error, commands.MissingPermissions):
        embed.description = "No tienes permisos para ejecutar este comando."
    elif isinstance(error, commands.BotMissingPermissions):
        embed.description = "El bot no tiene permisos suficientes."
    elif isinstance(error, commands.CommandOnCooldown):
        embed.description = f"Espera {error.retry_after:.1f} segundos antes de usar este comando nuevamente."
    else:
        embed.description = f"Ocurrió un error: ```{str(error)[:200]}```"
    
    try:
        await ctx.send(embed=embed)
    except:
        pass

# ==============================================================================
# COMANDOS DEL BOT
# ==============================================================================

# Comando de ayuda básico
@bot.tree.command(name="ayuda", description="Muestra información de ayuda")
async def ayuda(interaction: discord.Interaction):
    """Comando de ayuda"""
    embed = discord.Embed(
        title="🤖 Ayuda - SyncOps Bot",
        description="Sistema de tickets para gestión de incidencias",
        color=0x3498db,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="📋 Comandos Disponibles",
        value="""
        **/reporte** - Crear un nuevo ticket
        **/analisis** - Ver estadísticas de tickets
        **/ayuda** - Mostrar este mensaje
        """,
        inline=False
    )
    
    embed.add_field(
        name="🛠️ Uso Básico",
        value="""
        1. Usa `/reporte` para reportar un problema
        2. Adjunta una foto como evidencia
        3. Selecciona el motivo del reporte
        4. Se creará un ticket automáticamente
        """,
        inline=False
    )
    
    embed.add_field(
        name="📊 Análisis",
        value="Usa `/analisis` para ver estadísticas y métricas de los tickets.",
        inline=False
    )
    
    embed.add_field(
        name="🆘 Soporte",
        value="Si encuentras problemas, contacta al administrador del sistema.",
        inline=False
    )
    
    embed.set_footer(text="SyncOps Bot v1.0")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==============================================================================
# CARGAR COGS/MÓDULOS
# ==============================================================================

async def cargar_cogs():
    """Cargar todos los módulos del bot"""
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
    
    print("✅ Módulos cargados")

# ==============================================================================
# FUNCIÓN PRINCIPAL
# ==============================================================================

async def main():
    """Función principal de arranque del bot"""
    print("🚀 Iniciando SyncOps Discord Bot...")
    
    # Verificar archivos esenciales
    print("🔍 Verificando archivos esenciales...")
    
    essential_files = [
        ("Cogs/tickets.py", "src/discord_bot/cogs/tickets.py"),
        ("Config/settings.py", "src/discord_bot/config/settings.py"),
        ("Data/sitios.csv", "src/discord_bot/data/sitios.csv"),
        ("Core/database.py", "src/discord_bot/core/database.py"),
    ]
    
    all_files_ok = True
    for name, path in essential_files:
        if os.path.exists(path):
            print(f"   ✅ {name}")
        else:
            print(f"   ❌ {name} (no encontrado en {path})")
            all_files_ok = False
    
    if not all_files_ok:
        print("⚠️  Algunos archivos esenciales no fueron encontrados")
        print("💡 Verifica la estructura del proyecto")
    
    # Iniciar servidor web para health checks
    print("🌍 Iniciando servidor web para health checks...")
    health_server = HealthServer(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
    await health_server.start()
    
    # Cargar cogs
    await cargar_cogs()
    
    # Iniciar bot
    print("🔗 Conectando a Discord...")
    
    try:
        await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure as e:
        print(f"❌ ERROR DE AUTENTICACIÓN: Token de Discord inválido")
        print(f"💡 Razón: {e}")
        print("🔑 Regenera tu token en: https://discord.com/developers/applications")
    except discord.PrivilegedIntentsRequired as e:
        print(f"❌ ERROR DE INTENCIONES: Intents no habilitados")
        print(f"💡 Ve a Developer Portal → Bot → Privileged Gateway Intents")
        print(f"💡 Habilita: PRESENCE INTENT, SERVER MEMBERS INTENT, MESSAGE CONTENT INTENT")
    except KeyboardInterrupt:
        print("\n👋 Bot detenido manualmente")
    except Exception as e:
        print(f"💥 ERROR CRÍTICO: {e}")
        traceback.print_exc()
    finally:
        # Detener servidor web
        await health_server.stop()
        
        if not bot.is_closed():
            await bot.close()
        print("✅ Bot desconectado")

# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Programa terminado por el usuario")
    except Exception as e:
        print(f"💥 Error en ejecución principal: {e}")
        traceback.print_exc()
        sys.exit(1)
