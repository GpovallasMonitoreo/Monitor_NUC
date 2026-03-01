import os
import sys

# 1. Forzar que Python vea la raíz del proyecto antes de importar nada
base_path = os.path.dirname(os.path.abspath(__file__))
if base_path not in sys.path:
    sys.path.insert(0, base_path)

from src import create_app
from src.services.discord_service import DiscordBotService

# Crear la aplicación usando la fábrica
app = create_app()

# ==============================================================================
# 🤖 INICIO DEL BOT (Fuera del if __name__)
# ==============================================================================
try:
    discord_bot = DiscordBotService()
    discord_bot.start()
except Exception as e:
    print(f"❌ Error crítico al iniciar el bot de Discord: {e}")

if __name__ == '__main__':
    # Esto solo se usa para pruebas locales con 'python app.py'
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
