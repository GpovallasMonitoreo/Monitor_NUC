import os
from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# CONFIGURACIÓN BÁSICA - DISCORD
# ==============================================================================
DISCORD_BOT_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1448770446638973131
CANAL_GENERAL_ID = 1457449842107220123

# ==============================================================================
# 🗄️ SERVICIOS EXTERNOS (SUPABASE Y DRIVE)
# ==============================================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID") # 🆕 Añadido para guardar las imágenes

# ==============================================================================
# 🧠 LÓGICA DE NEGOCIO Y DEPARTAMENTOS
# ==============================================================================
DEPTO_SOPORTE = "Soporte Remoto Digital"
DEPTO_PAUTA = "Programación de Pauta"
DEPTO_CAMPO = "Operación Campo"
DEPTO_BIOBOX = "Op. Bio Box"        # 🆕 Nuevo departamento
DEPTO_INCIDENCIAS = "Incidencias"   # 🆕 Nuevo departamento

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
    },
    # 🆕 Configura aquí los IDs reales cuando los tengas
    DEPTO_BIOBOX: {
        "canal_id": 1476689174424719431, 
        "rol_id": 1476688510038577172,
        "alias": "BIOBOX"
    },
    DEPTO_INCIDENCIAS: {
        "canal_id": 1477602421332115527,
        "rol_id": 1477603909320179733,
        "alias": "INCIDENCIAS"
    }
}

MAPA_MOTIVOS = {
    "Pantalla Apagada": DEPTO_SOPORTE,
    "Pantalla Dañada": DEPTO_CAMPO,
    "Grafiti": DEPTO_CAMPO,
    "No se visualiza Pauta": DEPTO_SOPORTE,
    "Pauta Incorrecta": DEPTO_PAUTA,
    "Mantenimiento Preventivo": DEPTO_CAMPO, # 🆕 Agregado
    "Otro": DEPTO_SOPORTE
}

# ==============================================================================
# COLORES
# ==============================================================================
COLOR_EMBED = 0x3498DB
COLOR_EXITO = 0x2ECC71
COLOR_ALERTA = 0xE74C3C
COLOR_REASIGNADO = 0x9B59B6

# ==============================================================================
# SEGURIDAD
# ==============================================================================
PIN_SECRET = os.getenv("PIN_SECRET", "1234")
