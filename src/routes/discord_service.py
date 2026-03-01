import discord
from discord.ext import commands
import os
import asyncio
import threading
import logging

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
        self._setup_events()

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            logger.info(f"✅ BOT DISCORD CONECTADO: {self.bot.user.name}")
            try:
                logger.info("⏳ Sincronizando comandos con Discord...")
                synced = await self.bot.tree.sync()
                logger.info(f"✅ Sincronización exitosa: {len(synced)} comandos de tickets activos.")
            except Exception as e:
                logger.error(f"❌ Error al sincronizar comandos: {e}")

    async def _load_cogs(self):
        try:
            # Asegúrate de que la carpeta 'cogs' esté al mismo nivel que el entrypoint de tu app en Render
            await self.bot.load_extension("cogs.tickets")
            logger.info("✅ Módulo 'cogs.tickets' cargado correctamente.")
        except Exception as e:
            logger.error(f"❌ ERROR CARGANDO COGS: {e}")

    async def _run_bot(self):
        if not self.token:
            logger.error("❌ DISCORD_TOKEN no encontrado en las variables de entorno de Render.")
            return
            
        async with self.bot:
            await self._load_cogs()
            try:
                await self.bot.start(self.token)
            except Exception as e:
                logger.error(f"❌ Error de conexión con Discord: {e}")

    def _thread_runner(self):
        """Ejecuta el bot en su propio bucle de eventos asyncio."""
        # Creamos un nuevo loop específico para este hilo
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._run_bot())

    def start(self):
        """Inicia el bot en un hilo separado para no bloquear el Web Service principal."""
        if not self.running:
            self.running = True
            threading.Thread(target=self._thread_runner, daemon=True).start()
            logger.info("🚀 Servicio de Discord (Tickets) iniciado en segundo plano.")
