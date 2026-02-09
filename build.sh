#!/usr/bin/env bash
echo "🚀 Construyendo Monitor NUC System..."
echo "📁 Directorio: $(pwd)"
echo "🐍 Versión de Python: $(python --version)"

echo "📦 Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build completado"
