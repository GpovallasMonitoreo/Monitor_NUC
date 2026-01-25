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
        """Convierte valores a float de forma segura, evitando error 500"""
        try:
            if value is None or value == '': return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    # --- CÁLCULO CIENTÍFICO DE IMPACTO AMBIENTAL ---
    def _calculate_eco_impact(self):
        """
        Calcula el ahorro real al migrar de tecnología Legacy a NUC/LED Eficiente.
        Datos: 18 horas de uso diario.
        """
        # Consumo Promedio (Watts/Hora)
        watts_legacy = 450.0  # Pantalla vieja + Player antiguo
        watts_modern = 150.0  # Pantalla LED Nueva + NUC 11th Gen
        hours_active = 18.0   # Horas encendida al día
        
        # Ahorro: (Diferencia Watts * Horas * 365 días) / 1000 para kWh
        kwh_saved_annual = ((watts_legacy - watts_modern) * hours_active * 365) / 1000
        
        # Factor CO2 (México: ~0.42 kg CO2 por kWh generado)
        co2_tons = (kwh_saved_annual * 0.42) / 1000
        
        # Árboles equivalentes (1 árbol maduro absorbe ~22kg CO2/año)
        trees = int((kwh_saved_annual * 0.42) / 22)

        return {
            "kwh_saved": round(kwh_saved_annual, 2),
            "co2_tons": round(co2_tons, 2),
            "trees": trees,
            "efficiency_gain": "66%" 
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
                
                # Compatibilidad con datos viejos
                if not ctype:
                    t = f.get('type')
                    if t == 'installation': ctype = 'CAPEX'
                    elif t == 'sale': ctype = 'REVENUE'
                    else: ctype = 'OPEX'

                if ctype == 'CAPEX': capex += amt
                elif ctype == 'REVENUE': 
                    if rec == 'monthly': sales_total += (amt * 12)
                    else: sales_total += amt
                elif ctype == 'OPEX' and rec == 'monthly': opex_monthly += amt

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
            # Consultas DB seguras
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            # En tickets buscamos por 'sitio' o 'device_id' dependiendo de tu tabla
            tic_resp = self.client.table("tickets").select("*").eq("sitio", device_id).execute()
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()

            records = fin_resp.data if fin_resp and fin_resp.data else []
            tickets = tic_resp.data if tic_resp and tic_resp.data else []
            device_info = dev_resp.data[0] if dev_resp and dev_resp.data else {}

            data = {
                "device": device_info,
                "breakdown": records,
                "totals": {"capex": 0.0, "opex": 0.0, "revenue": 0.0, "roi": 0.0},
                "history": {"tickets": tickets, "downtime": device_info.get('disconnect_count', 0)},
                "eco": self._calculate_eco_impact()
            }

            for r in records:
                amt = self._safe_float(r.get('amount'))
                ctype = r.get('cost_type')
                rec = r.get('recurrence')
                
                # Compatibilidad
                if not ctype:
                    t = r.get('type')
                    if t == 'installation': ctype = 'CAPEX'
                    elif t == 'sale': ctype = 'REVENUE'
                    else: ctype = 'OPEX'

                if ctype == 'CAPEX': data['totals']['capex'] += amt
                elif ctype == 'OPEX' and rec == 'monthly': data['totals']['opex'] += amt
                elif ctype == 'REVENUE' and rec == 'monthly': data['totals']['revenue'] += amt

            margin = data['totals']['revenue'] - data['totals']['opex']
            if margin > 0: data['totals']['roi'] = data['totals']['capex'] / margin

            return data
        except Exception as e:
            logger.error(f"Error Device {device_id}: {e}")
            # Retornar estructura vacía para evitar error 500
            return {
                "device": {}, "breakdown": [], 
                "totals": {"capex": 0, "opex": 0, "revenue": 0, "roi": 0},
                "history": {"tickets": [], "downtime": 0},
                "eco": {"kwh_saved": 0, "co2_tons": 0, "trees": 0, "efficiency_gain": "0%"}
            }

    def save_cost_entry(self, payload):
        """Guarda un costo en la tabla finances"""
        try:
            record = {
                "device_id": payload.get('device_id'),
                "cost_type": payload.get('cost_type'),
                "category": payload.get('category'),
                "concept": payload.get('concept'),
                "amount": self._safe_float(payload.get('amount')),
                "recurrence": payload.get('recurrence', 'one_time'),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "created_at": datetime.now().isoformat(),
                "type": "sale" if payload.get('cost_type') == 'REVENUE' else "expense"
            }
            # Usamos insert para mantener historial
            self.client.table("finances").insert(record).execute()
            return True
        except Exception as e:
            logger.error(f"Error Save: {e}")
            return False
