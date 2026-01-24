import os
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# --- COSTOS GLOBALES Y VARIABLES (Valores por defecto) ---
# Se usan si la pantalla no tiene costos específicos registrados en 'finances'
GLOBAL_COSTS = {
    'infraestructura_base': 45000.0,  # Costo default pantalla + obra
    'opex_luz': 800.0,                # Costo luz mensual promedio
    'opex_internet': 500.0,           # Costo internet mensual promedio
    'manto_preventivo': 1500.0,       # Visita técnica estándar
    'incidencia_promedio': 3500.0     # Costo estimado si el ticket no tiene valor
}

class SupabaseService:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Faltan credenciales de Supabase en .env")
        self.client: Client = create_client(url, key)
        logger.info("✅ Conexión Supabase: Modo Financiero Avanzado")

    def get_financial_overview(self):
        """
        Dashboard Principal: Cruce de Ventas, CAPEX real, OPEX recurrente e Incidencias.
        """
        try:
            # 1. Traer datos crudos (Optimizado)
            finances = self.client.table("finances").select("*").execute().data
            tickets = self.client.table("tickets").select("costo_estimado, estatus").execute().data
            devices = self.client.table("devices").select("device_id, status, disconnect_count").execute().data

            # 2. Calcular CAPEX (Inversión Histórica)
            # Sumamos todo lo que sea recurrencia 'one_time' y tipo 'expense' (instalaciones, renovaciones)
            capex_total = sum(f['amount'] for f in finances if f.get('recurrence') == 'one_time' and f['type'] != 'sale')

            # 3. Calcular Ventas Anuales (Proyección)
            # Sumamos ventas mensuales * 12 + ventas únicas
            sales_monthly = sum(f['amount'] for f in finances if f['type'] == 'sale' and f.get('recurrence') == 'monthly')
            sales_one_time = sum(f['amount'] for f in finances if f['type'] == 'sale' and f.get('recurrence') == 'one_time')
            sales_annual = (sales_monthly * 12) + sales_one_time

            # 4. Calcular OPEX Mensual (Gasto Operativo)
            # Suma de rentas, luz, licencias mensuales registradas
            opex_monthly_db = sum(f['amount'] for f in finances if f.get('recurrence') == 'monthly' and f['type'] != 'sale')
            
            # Si no hay suficiente data, usamos un estimado base por número de pantallas activas
            active_screens = len(devices)
            if opex_monthly_db < 1000: # Si la DB está vacía, usamos default
                opex_monthly = active_screens * (GLOBAL_COSTS['opex_luz'] + GLOBAL_COSTS['opex_internet'])
            else:
                opex_monthly = opex_monthly_db

            # 5. Costo de Incidencias (Mantenimiento Correctivo)
            incident_costs = sum((t.get('costo_estimado') or GLOBAL_COSTS['incidencia_promedio']) for t in tickets)

            return {
                "kpis": {
                    "capex": capex_total,
                    "sales_annual": sales_annual,
                    "opex_monthly": opex_monthly,
                    "incidents": len(tickets),
                    "active_alerts": sum(1 for d in devices if d['status'] != 'online')
                },
                "financials": {
                    "months": ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun'], # Demo: En prod usar group_by date
                    "sales": [sales_monthly] * 6, 
                    "maintenance": [(opex_monthly + (incident_costs/6))] * 6 # Prorrateo simple para demo
                }
            }
        except Exception as e:
            logger.error(f"Error Overview: {e}")
            return None

    def get_device_detail(self, device_id):
        """
        Detalle TechView: Desglosa CAPEX, OPEX y Mantenimiento por categorías.
        Usa lógica 'Fallabck' a costos globales si no hay registros.
        """
        try:
            # Consultas en paralelo (conceptualmente)
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            tic_resp = self.client.table("tickets").select("*").eq("sitio", device_id).execute() # Asumiendo match por sitio/ID

            if not dev_resp.data: return None
            
            device = dev_resp.data[0]
            finances = fin_resp.data
            tickets = tic_resp.data

            # --- A. CÁLCULO CAPEX (Inversión) ---
            capex_real = sum(f['amount'] for f in finances if f.get('recurrence') == 'one_time' and f['type'] != 'sale')
            # Si es 0, asumimos costo global para no mostrar $0
            capex_final = capex_real if capex_real > 0 else GLOBAL_COSTS['infraestructura_base']

            # --- B. CÁLCULO OPEX (Mensual) ---
            opex_real = sum(f['amount'] for f in finances if f.get('recurrence') == 'monthly' and f['type'] != 'sale')
            opex_final = opex_real if opex_real > 0 else (GLOBAL_COSTS['opex_luz'] + GLOBAL_COSTS['opex_internet'])

            # --- C. VENTAS ---
            sales_monthly = sum(f['amount'] for f in finances if f['type'] == 'sale' and f.get('recurrence') == 'monthly')

            # --- D. INCIDENCIAS Y APAGADOS ---
            incident_cost = sum((t.get('costo_estimado') or 0) for t in tickets)
            downtime_count = device.get('disconnect_count', 0)

            # Estructura para el Frontend
            return {
                "device": device,
                "financials": {
                    "capex": capex_final,
                    "opex_monthly": opex_final,
                    "sales_monthly": sales_monthly,
                    "roi_months": (capex_final / (sales_monthly - opex_final)) if (sales_monthly - opex_final) > 0 else 0,
                    "total_project_cost": capex_final + incident_cost # CAPEX + Correctivos acumulados
                },
                "breakdown": {
                    # Enviamos los registros crudos para que el JS llene los formularios
                    "items": finances 
                },
                "history": {
                    "tickets": tickets,
                    "downtime": downtime_count
                }
            }

        except Exception as e:
            logger.error(f"Error Detalle {device_id}: {e}")
            return None

    def save_financial_record(self, data):
        """Guarda un nuevo costo desde TechView"""
        try:
            # Mapeamos los datos del formulario a la estructura DB
            record = {
                "device_id": data.get('device_id'),
                "type": data.get('type', 'expense'),         # expense / sale
                "category": data.get('category'),            # Infraestructura, Luz, etc.
                "recurrence": data.get('recurrence'),        # one_time / monthly
                "amount": float(data.get('amount', 0)),
                "description": data.get('description', ''),
                "date": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            }
            self.client.table("finances").insert(record).execute()
            return True
        except Exception as e:
            logger.error(f"Error guardando finanzas: {e}")
            return False
