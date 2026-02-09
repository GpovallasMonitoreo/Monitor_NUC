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
    "danada": "dañada"
}

def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""

    # 1. Convertir a minúsculas temporalmente para buscar
    texto_procesado = texto.lower()

    # 2. Reemplazar errores comunes (Búsqueda exacta)
    palabras = texto_procesado.split()
    palabras_corregidas = []
    
    for palabra in palabras:
        # Quitamos signos de puntuación para comparar
        limpia = re.sub(r'[^\w\s]', '', palabra)
        if limpia in CORRECCIONES:
            # Reemplazamos conservando puntuación si es posible (simplificado aquí)
            palabras_corregidas.append(CORRECCIONES[limpia])
        else:
            palabras_corregidas.append(palabra)
    
    texto_final = " ".join(palabras_corregidas)

    # 3. Eliminar espacios dobles y espacios al inicio/final
    texto_final = " ".join(texto_final.split())

    # 4. Capitalizar la primera letra de la frase (Tipo Oración)
    texto_final = texto_final.capitalize()

    return texto_final
