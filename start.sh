#!/usr/bin/env bash
# start.sh - Script de inicio para Render

echo "🚀 Iniciando Monitor NUC System..."
echo "📅 $(date)"
echo "📁 $(pwd)"
echo "🔧 Modo: $1"

# Configuración común
export PYTHONUNBUFFERED=1
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Verificar variables críticas
check_env_vars() {
    echo "🔍 Verificando variables de entorno..."
    
    if [ -z "$RENDER" ]; then
        echo "⚠️  RENDER no está definido (modo desarrollo asumido)"
    else
        echo "✅ Modo Render detectado"
    fi
    
    if [ -n "$PORT" ]; then
        echo "✅ Puerto: $PORT"
    else
        export PORT=10000
        echo "⚠️  PORT no definido, usando: $PORT"
    fi
}

# Iniciar servicio según parámetro
case "$1" in
    "flask")
        echo "🌐 Iniciando aplicación Flask..."
        check_env_vars
        
        # Configurar Flask
        export FLASK_APP=src/routes/app.py
        export FLASK_ENV=production
        
        echo "🏃‍♂️ Ejecutando Flask en puerto $PORT..."
        cd src/routes
        exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 app:app
        ;;
    
    "discord")
        echo "🤖 Iniciando Discord Bot..."
        check_env_vars
        
        # Verificar token de Discord
        if [ -z "$DISCORD_TOKEN" ]; then
            echo "❌ ERROR: DISCORD_TOKEN no está definido"
            echo "💡 Configúralo en Render.com → Environment Variables"
            exit 1
        fi
        
        echo "✅ Discord Token: Presente (${#DISCORD_TOKEN} caracteres)"
        
        # Verificar Supabase
        if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
            echo "⚠️  ADVERTENCIA: Credenciales de Supabase incompletas"
        else
            echo "✅ Supabase: Configurado"
        fi
        
        # Ejecutar bot
        echo "🏃‍♂️ Ejecutando bot..."
        cd src/discord_bot
        exec python main.py
        ;;
    
    *)
        echo "❌ Error: Debes especificar 'flask' o 'discord'"
        echo "📖 Uso: ./start.sh [flask|discord]"
        echo ""
        echo "Ejemplos:"
        echo "  ./start.sh flask    # Inicia la API Flask"
        echo "  ./start.sh discord  # Inicia el bot de Discord"
        exit 1
        ;;
esac
