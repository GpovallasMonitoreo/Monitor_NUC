import os
import sys
import logging
import atexit

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 1. Forzar que Python vea la raíz del proyecto antes de importar nada
base_path = os.path.dirname(os.path.abspath(__file__))
if base_path not in sys.path:
    sys.path.insert(0, base_path)

from src import create_app
from src.services.discord_service import DiscordBotService

# Crear la aplicación usando la fábrica
app = create_app()

# ==============================================================================
# 🤖 INICIO DEL BOT (Con manejo de errores mejorado)
# ==============================================================================
discord_bot = None

def iniciar_bot():
    """Inicializa y arranca el bot de Discord"""
    global discord_bot
    try:
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            logger.error("❌ DISCORD_TOKEN no está configurado en las variables de entorno")
            return None
            
        discord_bot = DiscordBotService()
        discord_bot.start()
        
        # Registrar la función de parada para cuando termine la app
        atexit.register(detener_bot)
        
        logger.info("✅ Bot de Discord iniciado correctamente")
        return discord_bot
    except Exception as e:
        logger.error(f"❌ Error crítico al iniciar el bot de Discord: {e}")
        import traceback
        traceback.print_exc()
        return None

def detener_bot():
    """Detiene el bot gracefulmente al cerrar la app"""
    global discord_bot
    if discord_bot:
        logger.info("Deteniendo bot de Discord...")
        discord_bot.stop()

# Iniciar el bot
discord_bot = iniciar_bot()

# ==============================================================================
# RUTA DE DIAGNÓSTICO (opcional, para verificar el estado del bot)
# ==============================================================================
@app.route('/bot-status')
def bot_status():
    """Endpoint para verificar el estado del bot"""
    if discord_bot and discord_bot.running:
        return {
            "status": "online",
            "bot_name": str(discord_bot.bot.user) if discord_bot.bot.user else "Conectando...",
            "guilds": len(discord_bot.bot.guilds) if discord_bot.bot.guilds else 0
        }
    return {"status": "offline"}

if __name__ == '__main__':
    # Esto solo se usa para pruebas locales con 'python app.py'
    port = int(os.environ.get('PORT', 8000))
    logger.info(f"🚀 Iniciando servidor Flask en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
