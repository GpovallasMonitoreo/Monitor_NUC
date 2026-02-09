#!/usr/bin/env bash
# build.sh - Script de construcción para Render

echo "🚀 Iniciando proceso de build..."
echo "📅 Fecha: $(date)"
echo "📁 Directorio: $(pwd)"
echo "🐍 Python: $(python --version)"

# Limpiar cache de pip
echo "🧹 Limpiando cache..."
pip cache purge

# Actualizar pip
echo "📦 Actualizando pip..."
python -m pip install --upgrade pip

# Instalar dependencias
echo "📥 Instalando dependencias..."
pip install -r requirements.txt

# Verificar instalación
echo "✅ Dependencias instaladas:"
pip list

# Verificar estructura de directorios
echo "📂 Verificando estructura..."
if [ -d "src/discord_bot" ]; then
    echo "✅ Directorio discord_bot encontrado"
else
    echo "❌ Directorio discord_bot NO encontrado"
    exit 1
fi

if [ -f "src/discord_bot/main.py" ]; then
    echo "✅ main.py encontrado"
else
    echo "❌ main.py NO encontrado"
    exit 1
fi

if [ -f "src/discord_bot/data/sitios.csv" ]; then
    echo "✅ sitios.csv encontrado"
else
    echo "⚠️  sitios.csv NO encontrado (se creará dummy si es necesario)"
    # Crear archivo dummy si no existe
    mkdir -p src/discord_bot/data
    echo "Sitio,Unidad" > src/discord_bot/data/sitios.csv
    echo "MX_TEST_001,ECOVALLAS" >> src/discord_bot/data/sitios.csv
fi

echo "🎉 Build completado exitosamente!"
