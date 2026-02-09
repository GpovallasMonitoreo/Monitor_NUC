import discord
from discord import app_commands
from discord.ext import commands
import datetime
import traceback
import asyncio
import sys
import os
import importlib.util
import json
import random

# ==============================================================================
# 🛠️ CARGA DE CONFIGURACIÓN
# ==============================================================================
try:
    # Ajustar ruta para la nueva estructura
    ruta_actual = os.path.dirname(__file__)
    discord_bot_dir = os.path.dirname(ruta_actual)
    src_dir = os.path.dirname(discord_bot_dir)
    
    # Añadir al path
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    
    # Importar settings
    import discord_bot.config.settings as settings
    print(f"✅ Configuración cargada desde nueva estructura.")
    
except Exception as e:
    print(f"⚠️ Error cargando configuración: {e}")
    settings = None

# El resto del archivo SIN CAMBIOS...
# Solo cambiar los imports al inicio:
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from discord_bot.core.database import db
from discord_bot.core.locations import loc_manager
from discord_bot.utils.catalogo_data import CATALOGO_SOPORTE
from discord_bot.utils.texto import limpiar_texto

# ... el resto del archivo SIN CAMBIOS ...
