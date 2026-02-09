"""
Configuración central para SyncOps Discord Bot
Versión segura para Render
"""

import os
import sys
from dotenv import load_dotenv

# ==============================================================================
# CONFIGURACIÓN DE RUTAS
# ==============================================================================

current_dir = os.path.dirname(os.path.abspath(__file__))
discord_bot_dir = os.path.dirname(current_dir)
src_dir = os.path.dirname(discord_bot_dir)
project_root = os.path.dirname(src_dir)

# Añadir rutas al sys.path
paths_to_add = [project_root, src_dir, discord_bot_dir]
for path in paths_to_add:
    if path not in sys.path:
        sys.path.insert(0, path)

print(f"⚙️  Cargando configuración desde: {current_dir}")

# ==============================================================================
# CARGAR VARIABLES DE ENTORNO
# ==============================================================================

# Intentar cargar .env desde múltiples ubicaciones
env_loaded = False
env_paths = [
    os.path.join(project_root, '.env'),
    os.path.join(current_dir, '.env'),
    '.env'
]

for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ Variables cargadas desde: {env_path}")
        env_loaded = True
        break

if not env_loaded:
    print("ℹ️  No se encontró archivo .env, usando variables del sistema")

# ==============================================================================
# CONFIGURACIÓN BÁSICA - DISCORD
# ==============================================================================

DISCORD_BOT_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 1448770446638973131))
CANAL_GENERAL_ID = int(os.getenv("CANAL_GENERAL_ID", 1457449842107220123))

# ==============================================================================
# VERIFICACIÓN DE CONFIGURACIÓN CRÍTICA
# ==============================================================================

def verificar_configuracion():
    """Verificar que toda la configuración crítica esté presente"""
    errores = []
    advertencias = []
    
    # Verificaciones CRÍTICAS
    if not DISCORD_BOT_TOKEN:
        errores.append("DISCORD_TOKEN no configurado")
    else:
        # Verificar formato básico del token
        if len(DISCORD_BOT_TOKEN) < 50:
            advertencias.append(f"Token muy corto ({len(DISCORD_BOT_TOKEN)} caracteres)")
    
    if not os.getenv("SUPABASE_URL"):
        advertencias.append("SUPABASE_URL no configurado")
    
    if not os.getenv("SUPABASE_KEY"):
        advertencias.append("SUPABASE_KEY no configurado")
    
    # Mostrar resultados
    if errores:
        print("❌ ERRORES DE CONFIGURACIÓN:")
        for error in errores:
            print(f"   • {error}")
    
    if advertencias:
        print("⚠️  ADVERTENCIAS:")
        for advertencia in advertencias:
            print(f"   • {advertencia}")
    
    if not errores and not advertencias:
        print("✅ Configuración verificada correctamente")
    
    return len(errores) == 0

# Ejecutar verificación
config_ok = verificar_configuracion()

# ==============================================================================
# BASE DE DATOS (SUPABASE)
# ==============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ==============================================================================
# LÓGICA DE NEGOCIO
# ==============================================================================

DEPTO_SOPORTE = "Soporte Remoto Digital"
DEPTO_PAUTA = "Programación de Pauta"
DEPTO_CAMPO = "Operación Campo"

DEPARTAMENTOS = {
    DEPTO_SOPORTE: {
        "canal_id": 1457581920685785120,
        "rol_id": 1457583148278878285,
        "alias": "SOPORTE",
        "emoji": "💻"
    },
    DEPTO_PAUTA: {
        "canal_id": 1457581887122964671,
        "rol_id": 1457584372176785418,
        "alias": "PAUTA",
        "emoji": "📺"
    },
    DEPTO_CAMPO: {
        "canal_id": 1457581950788309068,
        "rol_id": 1457584463176273996,
        "alias": "CAMPO",
        "emoji": "🔧"
    }
}

MAPA_MOTIVOS = {
    "Pantalla Apagada": DEPTO_SOPORTE,
    "Pantalla Dañada": DEPTO_CAMPO,
    "Grafiti": DEPTO_CAMPO,
    "No se visualiza Pauta": DEPTO_SOPORTE,
    "Pauta Incorrecta": DEPTO_PAUTA,
    "Otro": DEPTO_SOPORTE
}

# ==============================================================================
# COLORES PARA EMBEDS
# ==============================================================================

COLOR_EMBED = 0x3498DB        # Azul Discord
COLOR_EXITO = 0x2ECC71        # Verde éxito
COLOR_ALERTA = 0xE74C3C       # Rojo alerta
COLOR_REASIGNADO = 0x9B59B6   # Púrpura reasignación
COLOR_ANALISIS = 0xF39C12     # Naranja análisis
COLOR_INFO = 0xF1C40F         # Amarillo información
COLOR_ADVERTENCIA = 0xE67E22  # Naranja oscuro advertencia

# ==============================================================================
# TIEMPOS Y SLA
# ==============================================================================

SLA_DEFAULT = 24      # Horas por defecto
SLA_URGENTE = 4       # Horas para tickets urgentes
SLA_CRITICO = 1       # Horas para tickets críticos

# ==============================================================================
# SEGURIDAD
# ==============================================================================

PIN_SECRET = os.getenv("PIN_SECRET", "1234")

# ==============================================================================
# ENTORNO
# ==============================================================================

IS_RENDER = os.environ.get('RENDER') == 'true' or os.environ.get('PORT') is not None
ENVIRONMENT = "production" if IS_RENDER else "development"

print(f"🌍 Entorno: {ENVIRONMENT}")
print(f"🏗️  Estructura: {project_root}")
print(f"🔧 Configuración: {'✅ Lista' if config_ok else '❌ Con errores'}")

# ==============================================================================
# CONSTANTES ADICIONALES
# ==============================================================================

# Límites
MAX_TICKETS_POR_USUARIO = 10
MAX_SITIOS_AUTOCOMPLETE = 25
MAX_DESCRIPCION_LENGTH = 500

# Rutas de archivos
RUTA_SITIOS_CSV = os.path.join(discord_bot_dir, 'data', 'sitios.csv')
RUTA_LOGS = os.path.join(discord_bot_dir, 'logs')

# Crear directorio de logs si no existe
if not os.path.exists(RUTA_LOGS):
    os.makedirs(RUTA_LOGS, exist_ok=True)
