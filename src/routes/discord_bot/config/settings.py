"""
Configuración central para SyncOps Discord Bot
"""

import os
import sys
from dotenv import load_dotenv

# Añadir rutas para imports
current_dir = os.path.dirname(os.path.abspath(__file__))
discord_bot_dir = os.path.dirname(current_dir)
src_dir = os.path.dirname(discord_bot_dir)
project_root = os.path.dirname(src_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Cargar variables de entorno
load_dotenv()

print(f"⚙️  Cargando configuración desde: {current_dir}")

# ==============================================================================
# CONFIGURACIÓN BÁSICA - DISCORD
# ==============================================================================
DISCORD_BOT_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1448770446638973131
CANAL_GENERAL_ID = 1457449842107220123

# ==============================================================================
# VERIFICACIÓN DE CONFIGURACIÓN
# ==============================================================================
def verificar_configuracion():
    """Verificar que toda la configuración esté presente"""
    errores = []
    
    if not DISCORD_BOT_TOKEN:
        errores.append("DISCORD_TOKEN no configurado")
    
    if not os.getenv("SUPABASE_URL"):
        errores.append("SUPABASE_URL no configurado")
    
    if not os.getenv("SUPABASE_KEY"):
        errores.append("SUPABASE_KEY no configurado")
    
    if errores:
        print("⚠️ ADVERTENCIAS DE CONFIGURACIÓN:")
        for error in errores:
            print(f"   • {error}")
        return False
    
    print("✅ Configuración verificada correctamente")
    return True

# Ejecutar verificación
verificar_configuracion()

# ==============================================================================
# 🗄️ BASE DE DATOS (SUPABASE)
# ==============================================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ==============================================================================
# 🧠 LÓGICA DE NEGOCIO
# ==============================================================================
DEPTO_SOPORTE = "Soporte Remoto Digital"
DEPTO_PAUTA = "Programación de Pauta"
DEPTO_CAMPO = "Operación Campo"

DEPARTAMENTOS = {
    DEPTO_SOPORTE: {
        "canal_id": 1457581920685785120,
        "rol_id": 1457583148278878285,
        "alias": "SOPORTE"
    },
    DEPTO_PAUTA: {
        "canal_id": 1457581887122964671,
        "rol_id": 1457584372176785418,
        "alias": "PAUTA"
    },
    DEPTO_CAMPO: {
        "canal_id": 1457581950788309068,
        "rol_id": 1457584463176273996,
        "alias": "CAMPO"
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
COLOR_EMBED = 0x3498DB        # Azul
COLOR_EXITO = 0x2ECC71        # Verde
COLOR_ALERTA = 0xE74C3C       # Rojo
COLOR_REASIGNADO = 0x9B59B6   # Púrpura
COLOR_ANALISIS = 0xF39C12     # Naranja
COLOR_INFO = 0xF1C40F         # Amarillo

# ==============================================================================
# TIEMPOS Y SLA
# ==============================================================================
SLA_DEFAULT = 24  # Horas por defecto
SLA_URGENTE = 4   # Horas para tickets urgentes

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
