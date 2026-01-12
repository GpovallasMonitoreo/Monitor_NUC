# src/__init__.py

# Definimos las variables globales que usarán las rutas.
# Se inicializan como None y app.py las rellenará al arrancar.

storage = None
alerts = None
appsheet = None  # <--- AGREGADO: Necesario para que api.py no falle con error 500
monitor = None   # <--- AGREGADO: Necesario para el monitor en segundo plano
