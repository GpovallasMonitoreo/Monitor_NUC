def detectar_unidad(sitio_str: str) -> str:
    """
    Deduce la Unidad de Negocio basándose en el código del sitio.
    Orden de prioridad: BBOXXO (OXD) > BIOBOX (BB) > VIAVERDE (VV) > ECOVALLAS (EV)
    """
    sitio_upper = sitio_str.upper()
    
    # BBOXXO suele tener 'OXD' en su código según tu CSV
    if "_OXD_" in sitio_upper or "BBOXXO" in sitio_upper:
        return "BBOXXO"
    
    # BIOBOX suele ser BB (pero si no es OXD)
    elif "_BB_" in sitio_upper:
        return "BIOBOX"
    
    # VIAVERDE
    elif "_VV_" in sitio_upper:
        return "VIAVERDE"
    
    # ECOVALLAS
    elif "_EV_" in sitio_upper:
        return "ECOVALLAS"
    
    # Default por si acaso
    return "DESCONOCIDO"