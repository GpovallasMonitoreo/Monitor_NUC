import discord
from discord.ext import commands
import os
import asyncio
import logging
from threading import Thread

logger = logging.getLogger(__name__)

class DiscordBotService:
    def __init__(self):
        # Render inyecta las variables de entorno automáticamente
        self.token = os.getenv("DISCORD_TOKEN")
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
        self.running = False
        self._task = None
        self._setup_events()

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            logger.info(f"✅ BOT DISCORD CONECTADO: {self.bot.user.name}")
            logger.info(f"🌐 Servidores: {len(self.bot.guilds)}")
            try:
                logger.info("⏳ Sincronizando comandos con Discord...")
                
                # Sincronizar para un servidor específico (más rápido)
                if self.bot.guilds:
                    guild = self.bot.guilds[0]  # Tu servidor principal
                    self.bot.tree.copy_global_to(guild=guild)
                    synced = await self.bot.tree.sync(guild=guild)
                    logger.info(f"✅ Comandos sincronizados con servidor '{guild.name}': {len(synced)} comandos.")
                
                # También sincronizar globalmente
                synced_global = await self.bot.tree.sync()
                logger.info(f"✅ Sincronización global: {len(synced_global)} comandos.")
                
                # Listar comandos disponibles
                commands_list = [cmd.name for cmd in self.bot.tree.get_commands()]
                logger.info(f"📋 Comandos disponibles: {', '.join(commands_list)}")
                
            except Exception as e:
                logger.error(f"❌ Error al sincronizar comandos: {e}")
                import traceback
                traceback.print_exc()

    async def _load_cogs(self):
        try:
            # Verificar si el archivo existe
            cog_path = "cogs/tickets.py"
            if os.path.exists(cog_path):
                logger.info(f"✅ Archivo {cog_path} encontrado")
                await self.bot.load_extension("cogs.tickets")
                logger.info("✅ Módulo 'cogs.tickets' cargado correctamente.")
            else:
                # Intentar con ruta alternativa
                cog_path = "src/cogs/tickets.py"
                if os.path.exists(cog_path):
                    logger.info(f"✅ Archivo {cog_path} encontrado")
                    await self.bot.load_extension("src.cogs.tickets")
                else:
                    logger.error(f"❌ No se encuentra el archivo tickets.py en ninguna ruta")
                    
        except Exception as e:
            logger.error(f"❌ ERROR CARGANDO COGS: {e}")
            import traceback
            traceback.print_exc()

    async def _run_bot(self):
        if not self.token:
            logger.error("❌ DISCORD_TOKEN no encontrado en las variables de entorno de Render.")
            return
            
        try:
            async with self.bot:
                await self._load_cogs()
                logger.info("🚀 Iniciando conexión con Discord...")
                await self.bot.start(self.token)
        except Exception as e:
            logger.error(f"❌ Error de conexión con Discord: {e}")
            self.running = False

    def start(self):
        """Inicia el bot como una tarea asíncrona en el loop principal."""
        if not self.running:
            self.running = True
            try:
                # Obtener el loop de eventos actual o crear uno nuevo
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # No hay loop corriendo, crear uno nuevo
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Crear la tarea
                self._task = asyncio.create_task(self._run_bot())
                logger.info("🚀 Servicio de Discord iniciado como tarea asíncrona.")
                
            except Exception as e:
                logger.error(f"❌ Error al iniciar el bot: {e}")
                self.running = False

    def stop(self):
        """Detiene el bot correctamente."""
        if self.running and self._task:
            self.running = False
            self._task.cancel()
            logger.info("🛑 Servicio de Discord detenido.")
