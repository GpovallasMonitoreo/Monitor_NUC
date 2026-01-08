import requests
import time
import random

API_URL = "http://127.0.0.1:5000/api/report"

equipos = [f"MX_NUC_{i}" for i in range(1, 11)] # 10 Equipos simulados

while True:
    for equipo in equipos:
        payload = {
            "pc_name": equipo,
            "ip_address": f"192.168.1.{random.randint(100, 200)}",
            "cpu_percent": random.uniform(5, 95), # Random entre 5 y 95%
            "ram_percent": random.uniform(20, 80),
            "disk_percent": random.uniform(10, 50),
            "temperature": random.uniform(35, 85)
        }
        try:
            requests.post(API_URL, json=payload)
            print(f"Reporte enviado: {equipo}")
        except:
            print("Error conectando al servidor")
    
    time.sleep(2) # Enviar datos cada 2 segundos