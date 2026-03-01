import os
from src import create_app
from src.services.discord_service import DiscordBotService  # ⬅️ 1. Importamos el servicio

# Crear la aplicación usando la fábrica
app = create_app()

# ==============================================================================
# 🤖 INICIO DE SERVICIOS EN SEGUNDO PLANO
# ==============================================================================
# Al ponerlo aquí, garantizamos que el bot arranque en Render independientemente 
# de cómo se ejecute el servidor web.
try:
    discord_bot = DiscordBotService()
    discord_bot.start()  # ⬅️ 2. Arrancamos el hilo del bot
except Exception as e:
    print(f"❌ Error crítico al iniciar el bot de Discord: {e}")

# ==============================================================================
# 🌍 ARRANQUE DEL SERVIDOR WEB
# ==============================================================================
if __name__ == '__main__':
    # Detectar entorno
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.environ.get('PORT', 8000))
    
    print(f"🚀 Iniciando Argos System en puerto {port}")
    # Nota: use_reloader=False es crucial cuando usas hilos en segundo plano
    # para evitar que Flask inicie el bot dos veces durante el desarrollo.
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
