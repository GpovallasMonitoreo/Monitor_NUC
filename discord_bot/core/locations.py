import csv
import os
import sys

class LocationManager:
    def __init__(self):
        self.sitios = []
        self.cargar_sitios()

    def cargar_sitios(self):
        # Detectar si es ejecutable o script
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        path = os.path.join(base_dir, 'data', 'sitios.csv')
        self.sitios = []
        
        if not os.path.exists(path):
            print(f"⚠️ ERROR: No encuentro el archivo de sitios en: {path}")
            return

        codificaciones = ['utf-8', 'latin-1', 'cp1252']
        for codificacion in codificaciones:
            try:
                with open(path, newline='', encoding=codificacion) as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if not row: continue
                        # Unimos todas las columnas para que la busqueda sea global en la fila
                        # Ejemplo: "MX_CM_BB_001 - Perisur"
                        sitio_str = " - ".join([col.strip() for col in row if col.strip()])
                        self.sitios.append(sitio_str)
                    print(f"✅ Sitios cargados correctamente ({len(self.sitios)}).")
                    return
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"❌ Error leyendo CSV: {e}")
                return

    def buscar(self, query: str, limite=25):
        """Busca coincidencias parciales ignorando mayúsculas"""
        if not query: return self.sitios[:limite]
        
        query_b = query.lower().strip()
        resultados = []
        
        for s in self.sitios:
            if query_b in s.lower():
                resultados.append(s)
                if len(resultados) >= limite:
                    break
        return resultados

    def detectar_unidad(self, sitio_str: str) -> str:
        if not sitio_str: return "ECOVALLAS"
        s = sitio_str.upper()
        if "_VV_" in s: return "VIAVERDE"
        elif "_EV_" in s: return "ECOVALLAS"
        elif "_BB_" in s:
            return "BBOXXO" if "_OXD_" in s else "BIOBOX"
        return "ECOVALLAS"

loc_manager = LocationManager()