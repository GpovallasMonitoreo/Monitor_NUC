"""
Gestión de ubicaciones y sitios
"""

import csv
import os
import sys

class LocationManager:
    def __init__(self):
        self.sitios = []
        self.cargar_sitios()

    def cargar_sitios(self):
        """Cargar sitios desde CSV con múltiples rutas posibles"""
        
        # Rutas posibles para el archivo sitios.csv
        rutas_posibles = [
            # Ruta dentro del proyecto actual
            os.path.join(os.path.dirname(__file__), '..', 'data', 'sitios.csv'),
            # Ruta relativa desde la raíz del proyecto
            os.path.join(os.getcwd(), 'src', 'discord_bot', 'data', 'sitios.csv'),
            # Ruta absoluta común
            '/app/src/discord_bot/data/sitios.csv',  # Para Docker/Render
        ]
        
        path_encontrado = None
        for path in rutas_posibles:
            if os.path.exists(path):
                path_encontrado = path
                print(f"✅ Archivo sitios.csv encontrado en: {path}")
                break
        
        if not path_encontrado:
            print("❌ ERROR: No se encontró el archivo sitios.csv en ninguna ruta conocida")
            print("Rutas buscadas:")
            for path in rutas_posibles:
                print(f"  • {path}")
            return
        
        self.sitios = []
        
        codificaciones = ['utf-8', 'latin-1', 'cp1252', 'utf-8-sig']
        for codificacion in codificaciones:
            try:
                with open(path_encontrado, newline='', encoding=codificacion) as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if not row: 
                            continue
                        # Unimos todas las columnas para que la búsqueda sea global en la fila
                        sitio_str = " - ".join([col.strip() for col in row if col.strip()])
                        if sitio_str:  # Solo añadir si no está vacío
                            self.sitios.append(sitio_str)
                    
                    print(f"✅ {len(self.sitios)} sitios cargados desde {path_encontrado}")
                    return
                    
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"❌ Error leyendo CSV con codificación {codificacion}: {e}")
        
        print("❌ No se pudo leer el archivo sitios.csv con ninguna codificación conocida")

    def buscar(self, query: str, limite=25):
        """Busca coincidencias parciales ignorando mayúsculas"""
        if not self.sitios:
            self.cargar_sitios()
            
        if not query: 
            return self.sitios[:limite]
        
        query_b = query.lower().strip()
        resultados = []
        
        for s in self.sitios:
            if query_b in s.lower():
                resultados.append(s)
                if len(resultados) >= limite:
                    break
        
        return resultados

    def detectar_unidad(self, sitio_str: str) -> str:
        """Detectar unidad de negocio basada en el código del sitio"""
        if not sitio_str: 
            return "ECOVALLAS"
        
        s = sitio_str.upper()
        
        # Orden de prioridad según los prefijos
        if "_OXD_" in s or "BBOXXO" in s:
            return "BBOXXO"
        elif "_BB_" in s:
            return "BIOBOX"
        elif "_VV_" in s:
            return "VIAVERDE"
        elif "_EV_" in s:
            return "ECOVALLAS"
        else:
            # Intentar detectar por palabras clave
            if "BBOXXO" in s:
                return "BBOXXO"
            elif "BIOBOX" in s:
                return "BIOBOX"
            elif "VIAVERDE" in s:
                return "VIAVERDE"
            elif "ECOVALLAS" in s:
                return "ECOVALLAS"
        
        return "ECOVALLAS"  # Default

# Instancia global del gestor de ubicaciones
loc_manager = LocationManager()
