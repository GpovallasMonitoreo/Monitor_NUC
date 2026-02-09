"""
Utilidades para procesamiento de texto
"""

import re

# Diccionario de correcciones comunes en tu operación
CORRECCIONES = {
    "pantala": "pantalla",
    "imagene": "imagen",
    "senial": "señal",
    "coneccion": "conexión",
    "conecion": "conexión",
    "pauta": "pauta",
    "grafiti": "grafiti",
    "graffiti": "grafiti",
    "reinicio": "reinicio",
    "apagada": "apagada",
    "danada": "dañada",
    "dañada": "dañada",
    "operacion": "operación",
    "operaciones": "operaciones",
    "tecnologia": "tecnología",
    "nuc": "NUC",
    "ups": "UPS",
    "cfe": "CFE",
    "vpn": "VPN",
    "utp": "UTP",
    "poe": "POE",
    "sim": "SIM",
    "sla": "SLA"
}

def limpiar_texto(texto: str) -> str:
    """
    Limpia y normaliza texto, corrigiendo errores comunes.
    
    Args:
        texto: Texto a limpiar
        
    Returns:
        Texto limpio y normalizado
    """
    if not texto:
        return ""

    # 1. Convertir a minúsculas temporalmente para buscar
    texto_procesado = texto.lower()

    # 2. Reemplazar errores comunes
    palabras = texto_procesado.split()
    palabras_corregidas = []
    
    for palabra in palabras:
        # Quitamos signos de puntuación para comparar
        limpia = re.sub(r'[^\w\s]', '', palabra)
        
        # Buscar corrección en el diccionario
        if limpia in CORRECCIONES:
            palabras_corregidas.append(CORRECCIONES[limpia])
        else:
            palabras_corregidas.append(palabra)
    
    texto_final = " ".join(palabras_corregidas)

    # 3. Eliminar espacios dobles y espacios al inicio/final
    texto_final = " ".join(texto_final.split())

    # 4. Capitalizar la primera letra de la frase
    if texto_final:
        texto_final = texto_final[0].upper() + texto_final[1:]

    return texto_final

def truncar_texto(texto: str, max_length: int = 100) -> str:
    """
    Trunca texto a una longitud máxima.
    
    Args:
        texto: Texto a truncar
        max_length: Longitud máxima
        
    Returns:
        Texto truncado con "..." si es necesario
    """
    if not texto:
        return ""
    
    if len(texto) <= max_length:
        return texto
    
    return texto[:max_length - 3] + "..."

def formatear_lista(items: list, max_items: int = 5) -> str:
    """
    Formatea una lista de items para mostrarla en Discord.
    
    Args:
        items: Lista de items
        max_items: Máximo número de items a mostrar
        
    Returns:
        String formateado
    """
    if not items:
        return "• Ninguno"
    
    # Limitar número de items
    items_mostrar = items[:max_items]
    
    # Formatear
    resultado = ""
    for i, item in enumerate(items_mostrar, 1):
        resultado += f"{i}. {item}\n"
    
    # Añadir indicador si hay más items
    if len(items) > max_items:
        resultado += f"... y {len(items) - max_items} más"
    
    return resultado.strip()
