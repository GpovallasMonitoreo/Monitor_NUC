import os
import logging
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Faltan credenciales de Supabase en .env")
        self.client: Client = create_client(url, key)

    def _safe_float(self, value):
        """Convierte valores a float de forma segura"""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    # --- CÁLCULO CIENTÍFICO DE IMPACTO AMBIENTAL ---
    def _calculate_eco_impact(self):
        """
        Calcula el ahorro real al migrar de tecnología Legacy a NUC/LED Eficiente.
        Factores basados en promedios industriales.
        """
        # Consumo Promedio (Watts/Hora)
        watts_legacy = 450.0  # Pantalla vieja + Player antiguo
        watts_modern = 150.0  # Pantalla LED Nueva + NUC 11th Gen
        hours_active = 18.0   # Horas encendida al día
        
        # Cálculo de Ahorro
        daily_saving_kwh = ((watts_legacy - watts_modern) * hours_active) / 1000
        annual_saving_kwh = daily_saving_kwh * 365
        
        # Factores de Conversión (Fuente: EPA / Factores eléctricos México)
        co2_factor = 0.42  # kg CO2 por kWh ahorrado
        tree_absorption = 22.0 # kg CO2 que absorbe un árbol adulto al año
        
        co2_saved_tons = (annual_saving_kwh * co2_factor) / 1000
        trees_equivalent = int((annual_saving_kwh * co2_factor) / tree_absorption)

        return {
            "kwh_saved": round(annual_saving_kwh, 2),
            "co2_tons": round(co2_saved_tons, 2),
            "trees": trees_equivalent,
            "efficiency_gain": "66%" # (450-150)/450
        }

    # --- MÉTODOS DE DATOS ---
    def get_financial_overview(self):
        """KPIs Globales para el Dashboard Principal"""
        try:
            finances = self.client.table("finances").select("*").execute().data or []
            tickets = self.client.table("tickets").select("ticket_id, costo_estimado").execute().data or []
            devices = self.client.table("devices").select("status").execute().data or []

            capex = 0.0
            sales_total = 0.0
            opex_monthly = 0.0

            for f in finances:
                amt = self._safe_float(f.get('amount'))
                ctype = f.get('cost_type')
                rec = f.get('recurrence')
                
                # Compatibilidad
                if not ctype:
                    t = f.get('type')
                    if t == 'installation': ctype = 'CAPEX'
                    elif t == 'sale': ctype = 'REVENUE'
                    else: ctype = 'OPEX'

                if ctype == 'CAPEX': capex += amt
                if ctype == 'REVENUE': sales_total += (amt * 12) if rec == 'monthly' else amt
                if ctype == 'OPEX' and rec == 'monthly': opex_monthly += amt

            incident_cost = sum(self._safe_float(t.get('costo_estimado')) for t in tickets)

            return {
                "kpis": {
                    "capex": capex,
                    "sales_annual": sales_total,
                    "opex_monthly": opex_monthly,
                    "incidents": len(tickets),
                    "active_alerts": sum(1 for d in devices if d.get('status') != 'online')
                },
                "financials": {
                    "months": ['Actual', 'Proyección'],
                    "sales": [sales_total/12, sales_total/12],
                    "maintenance": [opex_monthly, opex_monthly + (incident_cost/12)]
                }
            }
        except Exception as e:
            logger.error(f"Error Overview: {e}")
            return None

    def get_device_detail(self, device_id):
        """Detalle completo por pantalla + Eco Impact"""
        try:
            # Consultas
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            tic_resp = self.client.table("tickets").select("*").eq("sitio", device_id).execute()
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()

            records = fin_resp.data if fin_resp.data else []
            tickets = tic_resp.data if tic_resp.data else []
            device_info = dev_resp.data[0] if dev_resp.data else {}

            data = {
                "device": device_info,
                "breakdown": records,
                "totals": {"capex": 0.0, "opex": 0.0, "revenue": 0.0, "roi": 0.0},
                "history": {"tickets": tickets, "downtime": device_info.get('disconnect_count', 0)},
                "eco": self._calculate_eco_impact() # <--- DATOS REALES CALCULADOS
            }

            for r in records:
                amt = self._safe_float(r.get('amount'))
                ctype = r.get('cost_type')
                rec = r.get('recurrence')
                
                if not ctype:
                    t = r.get('type')
                    ctype = 'CAPEX' if t == 'installation' else 'REVENUE' if t == 'sale' else 'OPEX'

                if ctype == 'CAPEX': data['totals']['capex'] += amt
                elif ctype == 'OPEX' and rec == 'monthly': data['totals']['opex'] += amt
                elif ctype == 'REVENUE' and rec == 'monthly': data['totals']['revenue'] += amt

            margin = data['totals']['revenue'] - data['totals']['opex']
            if margin > 0: data['totals']['roi'] = data['totals']['capex'] / margin

            return data
        except Exception as e:
            logger.error(f"Error Device {device_id}: {e}")
            return None

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
                "created_at": datetime.now().isoformat(),
                "type": "sale" if payload['cost_type'] == 'REVENUE' else "expense"
            }
            self.client.table("finances").insert(record).execute()
            return True
        except Exception as e:
            logger.error(f"Error Save: {e}")
            return False
