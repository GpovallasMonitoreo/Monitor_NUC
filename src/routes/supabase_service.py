import os
import logging
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# CONFIGURACIÓN DE COSTOS DEFAULT (Si no hay datos en DB)
DEFAULTS = {
    'capex_screen': 450000.0,
    'opex_light': 800.0,
    'opex_internet': 500.0
}

class SupabaseService:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key: raise ValueError("Faltan credenciales Supabase")
        self.client: Client = create_client(url, key)

    def get_device_financials(self, device_id):
        """Recupera todos los costos de una pantalla y los estructura para TechView"""
        try:
            # 1. Obtener registros financieros crudos
            resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            records = resp.data

            # 2. Estructura de retorno vacía
            data = {
                "capex": {},
                "opex": {},
                "maintenance": {},
                "lifecycle": {},
                "revenue": {},
                "totals": {"capex": 0, "opex_monthly": 0, "sales_monthly": 0}
            }

            # 3. Llenar estructura y calcular totales
            for r in records:
                ctype = r.get('cost_type', '').lower()
                concept = r.get('concept', 'varios')
                amount = float(r.get('amount', 0))

                # Guardar valor por concepto para llenar los inputs del HTML
                # Ej: data['capex']['Pantalla'] = 50000
                if ctype in data:
                    data[ctype][concept] = amount

                # Sumar totales
                if ctype == 'capex':
                    data['totals']['capex'] += amount
                elif ctype == 'opex' and r.get('recurrence') == 'monthly':
                    data['totals']['opex_monthly'] += amount
                elif ctype == 'revenue' and r.get('recurrence') == 'monthly':
                    data['totals']['sales_monthly'] += amount

            # Calcular ROI
            margin = data['totals']['sales_monthly'] - data['totals']['opex_monthly']
            data['totals']['roi'] = (data['totals']['capex'] / margin) if margin > 0 else 0

            return data

        except Exception as e:
            logger.error(f"Error get_device_financials: {e}")
            return None

    def save_cost_entry(self, payload):
        """Guarda un costo individual desde los formularios de TechView"""
        try:
            # Payload esperado: { device_id, cost_type, category, concept, amount, recurrence }
            record = {
                "device_id": payload['device_id'],
                "cost_type": payload['cost_type'], # CAPEX, OPEX, etc.
                "category": payload['category'],   # Infraestructura, Suministros...
                "concept": payload['concept'],     # Pantalla, Luz...
                "amount": float(payload['amount']),
                "recurrence": payload.get('recurrence', 'one_time'),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "created_at": datetime.now().isoformat()
            }
            
            # Upsert: Si ya existe un registro para ese concepto y dispositivo, lo actualizamos (opcional, o insertar nuevo)
            # Para historial, mejor insert. Para "configuración actual", mejor upsert o delete+insert.
            # Aquí usaremos INSERT para mantener historial completo.
            self.client.table("finances").insert(record).execute()
            return True
        except Exception as e:
            logger.error(f"Error saving cost: {e}")
            return False
