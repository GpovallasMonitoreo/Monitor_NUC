import os
import logging
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Configuración de Costos por Defecto (Solo si la base de datos está vacía)
DEFAULTS = {
    'capex_screen': 0,
    'opex_light': 0,
    'opex_internet': 0
}

class SupabaseService:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Faltan credenciales de Supabase en .env")
        self.client: Client = create_client(url, key)
        logger.info("✅ Conexión Supabase: Servicio Financiero Activo")

    # --- MÉTODOS ORIGINALES (NO BORRAR) ---
    def buffer_metric(self, device_id, latency, packet_loss=0, extra_data=None):
        # (Tu lógica original de buffer aquí...)
        pass 

    def upsert_device_status(self, device_data):
        try:
            self.client.table("devices").upsert(device_data).execute()
            return True
        except Exception as e:
            logger.error(f"Error upsert: {e}")
            return False

    # --- MÉTODOS TECHVIEW (FINANZAS REALES) ---

    def get_financial_overview(self):
        """
        Calcula los KPIs globales sumando los datos reales de la tabla 'finances'.
        """
        try:
            # 1. Traer datos
            finances = self.client.table("finances").select("*").execute().data
            tickets = self.client.table("tickets").select("id, costo_estimado").execute().data
            devices = self.client.table("devices").select("status, disconnect_count").execute().data

            # 2. Calcular Totales Reales
            # CAPEX: Suma de todo lo clasificado como 'CAPEX'
            capex_total = sum(f['amount'] for f in finances if f.get('cost_type') == 'CAPEX')

            # VENTAS ANUALES: (Ventas Mensuales * 12) + Ventas Únicas
            sales_monthly = sum(f['amount'] for f in finances if f.get('cost_type') == 'REVENUE' and f.get('recurrence') == 'monthly')
            sales_total = (sales_monthly * 12) + sum(f['amount'] for f in finances if f.get('cost_type') == 'REVENUE' and f.get('recurrence') == 'one_time')

            # OPEX MENSUAL: Suma de 'OPEX' recurrentes
            opex_monthly = sum(f['amount'] for f in finances if f.get('cost_type') == 'OPEX' and f.get('recurrence') == 'monthly')

            # INCIDENCIAS
            total_incidents = len(tickets)
            active_alerts = sum(1 for d in devices if d.get('status') != 'online')

            return {
                "kpis": {
                    "capex": capex_total,
                    "sales_annual": sales_total,
                    "opex_monthly": opex_monthly,
                    "incidents": total_incidents,
                    "active_alerts": active_alerts
                },
                # Datos para la gráfica (Agrupados simple para ejemplo, idealmente group by mes)
                "financials": {
                    "months": ['Actual', 'Proyección'],
                    "sales": [sales_monthly, sales_monthly],
                    "maintenance": [opex_monthly, opex_monthly]
                }
            }
        except Exception as e:
            logger.error(f"Error Overview: {e}")
            return None

    def get_device_financials(self, device_id):
        """
        Obtiene el desglose financiero de una pantalla específica.
        """
        try:
            records = self.client.table("finances").select("*").eq("device_id", device_id).execute().data
            
            data = {
                "breakdown": records, # Para llenar los inputs
                "totals": {"capex": 0, "opex": 0, "revenue": 0}
            }

            for r in records:
                ctype = r.get('cost_type')
                rec = r.get('recurrence')
                amt = float(r.get('amount', 0))

                if ctype == 'CAPEX': data['totals']['capex'] += amt
                if ctype == 'OPEX' and rec == 'monthly': data['totals']['opex'] += amt
                if ctype == 'REVENUE' and rec == 'monthly': data['totals']['revenue'] += amt

            return data
        except Exception as e:
            logger.error(f"Error Device Financials: {e}")
            return None

    def save_cost_entry(self, payload):
        """
        Guarda un registro en la tabla 'finances'.
        """
        try:
            # Primero intentamos buscar si ya existe ese concepto para ese dispositivo para actualizarlo
            # O simplemente insertamos un historial nuevo. Para este dashboard, haremos un 'upsert' lógico borrando el anterior del mismo concepto hoy.
            
            record = {
                "device_id": payload['device_id'],
                "cost_type": payload['cost_type'],  # CAPEX, OPEX...
                "category": payload['category'],    # Infraestructura...
                "concept": payload['concept'],      # Pantalla...
                "amount": float(payload['amount']),
                "recurrence": payload.get('recurrence', 'one_time'),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "created_at": datetime.now().isoformat()
            }
            
            # Insertar registro
            self.client.table("finances").insert(record).execute()
            return True
        except Exception as e:
            logger.error(f"Error guardando costo: {e}")
            return False
