import os
from src import create_app

# Crear la aplicación usando la fábrica
app = create_app()

if __name__ == '__main__':
    # Detectar entorno
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.environ.get('PORT', 8000))
    
    print(f"🚀 Iniciando Argos System en puerto {port}")
    print(f"📊 Sistema Principal: /api/*")
    print(f"💰 TechView Finanzas: /techview/*")
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
