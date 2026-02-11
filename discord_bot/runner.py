import asyncio
import threading
from .main import main as bot_main


def start_bot():
    """Arranca el bot en un hilo separado sin bloquear Flask"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot_main())


def run_discord_bot_background():
    """Lanza el bot en segundo plano"""
    thread = threading.Thread(target=start_bot, daemon=True)
    thread.start()
