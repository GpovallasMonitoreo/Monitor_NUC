import os
import logging
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key: raise ValueError("Faltan credenciales .env")
        self.client: Client = create_client(url, key)

    def _safe_float(self, value):
        """Convierte cualquier cosa a número. Si falla, devuelve 0.0"""
        try:
            if value is None: return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    # --- DASHBOARD GENERAL ---
    def get_financial_overview(self):
        try:
            # Consultas seguras
            finances = self.client.table("finances").select("*").execute().data or []
            tickets = self.client.table("tickets").select("ticket_id, costo_estimado").execute().data or []
            devices = self.client.table("devices").select("status").execute().data or []

            capex = 0.0
            sales_mensual = 0.0
            opex_mensual = 0.0

            # Procesar finanzas con protección anti-errores
            for f in finances:
                amt = self._safe_float(f.get('amount'))
                ctype = f.get('cost_type')
                rec = f.get('recurrence')
                
                # Compatibilidad con datos viejos (si cost_type es null)
                if not ctype:
                    old_type = f.get('type')
                    if old_type == 'installation': ctype = 'CAPEX'
                    elif old_type == 'sale': ctype = 'REVENUE'
                    else: ctype = 'OPEX'

                if ctype == 'CAPEX': capex += amt
                if ctype == 'REVENUE' and rec == 'monthly': sales_mensual += amt
                if ctype == 'OPEX' and rec == 'monthly': opex_mensual += amt

            # Procesar Tickets (Costo estimado)
            incident_cost = sum(self._safe_float(t.get('costo_estimado')) for t in tickets)

            return {
                "kpis": {
                    "capex": capex,
                    "sales_annual": sales_mensual * 12,
                    "opex_monthly": opex_mensual,
                    "incidents": len(tickets),
                    "active_alerts": sum(1 for d in devices if d.get('status') != 'online')
                },
                "financials": {
                    "months": ['Actual', 'Proy.'],
                    "sales": [sales_mensual, sales_mensual],
                    "maintenance": [opex_mensual, opex_mensual + (incident_cost/12)]
                }
            }
        except Exception as e:
            logger.error(f"Error Overview: {e}")
            # Retornar vacíos para no romper el front
            return {"kpis": {"capex": 0, "sales_annual": 0, "opex_monthly": 0, "incidents": 0, "active_alerts": 0}, "financials": {}}

    # --- DETALLE DISPOSITIVO (SOLUCIÓN ID CON ESPACIOS) ---
    def get_device_detail(self, device_id):
        try:
            # Buscar finances por ID
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            records = fin_resp.data if fin_resp.data else []

            data = {
                "breakdown": records, # Para rellenar inputs
                "totals": {"capex": 0.0, "opex": 0.0, "revenue": 0.0, "roi": 0.0}
            }

            for r in records:
                amt = self._safe_float(r.get('amount'))
                ctype = r.get('cost_type')
                
                # Lógica simple de asignación
                if ctype == 'CAPEX': 
                    data['totals']['capex'] += amt
                elif ctype == 'OPEX' and r.get('recurrence') == 'monthly': 
                    data['totals']['opex'] += amt
                elif ctype == 'REVENUE': 
                    data['totals']['revenue'] += amt

            # ROI
            margin = data['totals']['revenue'] - data['totals']['opex']
            if margin > 0:
                data['totals']['roi'] = data['totals']['capex'] / margin

            return data
        except Exception as e:
            logger.error(f"Error Device {device_id}: {e}")
            return {"breakdown": [], "totals": {"capex": 0, "opex": 0, "revenue": 0}}

    def save_cost_entry(self, payload):
        try:
            record = {
                "device_id": payload['device_id'],
                "cost_type": payload['cost_type'],
                "category": payload['category'],
                "concept": payload['concept'],
                "amount": self._safe_float(payload['amount']),
                "recurrence": payload.get('recurrence', 'one_time'),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "type": "sale" if payload['cost_type'] == 'REVENUE' else "expense"
            }
            self.client.table("finances").insert(record).execute()
            return True
        except Exception as e:
            logger.error(f"Save Error: {e}")
            return False
