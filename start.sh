#!/usr/bin/env bash

echo "🚀 Iniciando Monitor NUC System..."
echo "📁 Directorio: $(pwd)"
echo "⚙️ Modo: $1"

case "$1" in
    "flask")
        echo "🌐 Iniciando aplicación Flask..."
        export FLASK_APP=src/routes/app.py
        export FLASK_ENV=production
        cd src/routes
        exec python app.py
        ;;
    "discord")
        echo "🤖 Iniciando Discord Bot..."
        cd src/discord_bot
        exec python main.py
        ;;
    *)
        echo "❌ Error: Especifica 'flask' o 'discord' como argumento"
        echo "📖 Uso: ./start.sh [flask|discord]"
        exit 1
        ;;
esac
