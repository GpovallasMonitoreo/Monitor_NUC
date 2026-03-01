# src/services/discord_service.py
import discord
from discord.ext import commands
import os
import asyncio
import logging
import threading
from threading import Thread

logger = logging.getLogger(__name__)

class DiscordBotService:
    def __init__(self):
        self.token = os.getenv("DISCORD_TOKEN")
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
        self.running = False
        self.loop = None
        self.thread = None
        self._setup_events()

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            logger.info(f"✅ BOT DISCORD CONECTADO: {self.bot.user.name}")
            logger.info(f"🌐 Servidores: {len(self.bot.guilds)}")
            
            # Sincronizar comandos
            try:
                logger.info("⏳ Sincronizando comandos con Discord...")
                
                # Si hay servidores, sincronizar con el primero
                if self.bot.guilds:
                    guild = self.bot.guilds[0]
                    self.bot.tree.copy_global_to(guild=guild)
                    synced = await self.bot.tree.sync(guild=guild)
                    logger.info(f"✅ Comandos sincronizados con '{guild.name}': {len(synced)} comandos.")
                
                # Sincronización global
                synced_global = await self.bot.tree.sync()
                logger.info(f"✅ Sincronización global: {len(synced_global)} comandos.")
                
                # Listar comandos
                commands_list = [cmd.name for cmd in self.bot.tree.get_commands()]
                logger.info(f"📋 Comandos disponibles: {', '.join(commands_list)}")
                
            except Exception as e:
                logger.error(f"❌ Error sincronizando comandos: {e}")

        @self.bot.event
        async def on_command_error(ctx, error):
            logger.error(f"Error en comando: {error}")

    async def _load_cogs(self):
        try:
            # Intentar cargar desde diferentes rutas
            rutas_posibles = [
                "cogs.tickets",
                "src.cogs.tickets",
                "app.cogs.tickets"
            ]
            
            for ruta in rutas_posibles:
                try:
                    await self.bot.load_extension(ruta)
                    logger.info(f"✅ Módulo '{ruta}' cargado correctamente.")
                    return
                except (commands.ExtensionNotFound, ImportError):
                    continue
                    
            logger.error("❌ No se pudo cargar el módulo tickets.py")
                    
        except Exception as e:
            logger.error(f"❌ ERROR CARGANDO COGS: {e}")

    def _run_bot_in_thread(self):
        """Ejecuta el bot en un hilo con su propio loop de asyncio"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        async def start_bot():
            if not self.token:
                logger.error("❌ DISCORD_TOKEN no encontrado")
                return
                
            try:
                async with self.bot:
                    await self._load_cogs()
                    logger.info("🚀 Iniciando conexión con Discord...")
                    await self.bot.start(self.token)
            except Exception as e:
                logger.error(f"❌ Error en el bot: {e}")
                self.running = False

        try:
            self.loop.run_until_complete(start_bot())
        except Exception as e:
            logger.error(f"❌ Error en el loop: {e}")

    def start(self):
        """Inicia el bot en un hilo separado (compatible con Flask)"""
        if not self.running:
            self.running = True
            self.thread = Thread(target=self._run_bot_in_thread, daemon=True)
            self.thread.start()
            logger.info("🚀 Servicio de Discord iniciado en hilo separado.")

    def stop(self):
        """Detiene el bot correctamente"""
        if self.running and self.loop:
            self.running = False
            # Cancelar tareas pendientes
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            self.loop.call_soon_threadsafe(self.loop.stop)
            logger.info("🛑 Servicio de Discord detenido.")
