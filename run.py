# run.py
import os
from src import create_app

# Detectar entorno
debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
port = int(os.environ.get('PORT', 8000))

# Crear la aplicación usando la fábrica
app = create_app()

if __name__ == '__main__':
    print(f"🚀 Iniciando Argos System en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
