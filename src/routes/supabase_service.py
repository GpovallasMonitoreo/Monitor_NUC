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
        """Evita que el sistema se caiga por valores nulos"""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _calculate_eco_impact(self):
        """
        Cálculo real de ahorro energético (Legacy vs Moderno).
        Datos base: 18 horas de uso diario.
        """
        watts_legacy = 450.0  # Pantalla vieja + Player
        watts_modern = 150.0  # Pantalla Nueva + NUC 11th
        hours = 18.0
        
        # Ahorro kWh Anual
        kwh_saved = ((watts_legacy - watts_modern) * hours * 365) / 1000
        
        # Factor CO2 (0.42 kg/kWh México)
        co2_tons = (kwh_saved * 0.42) / 1000
        trees = int((kwh_saved * 0.42) / 22) # 22kg absorción árbol

        return {
            "kwh_saved": round(kwh_saved, 2),
            "co2_tons": round(co2_tons, 2),
            "trees": trees,
            "efficiency_gain": "66%"
        }

    # --- DASHBOARD GENERAL ---
    def get_financial_overview(self):
        try:
            finances = self.client.table("finances").select("*").execute().data or []
            tickets = self.client.table("tickets").select("id").execute().data or []
            
            capex_total = 0.0
            opex_monthly_total = 0.0
            sales_monthly_total = 0.0

            for f in finances:
                # Sumar CAPEX (Todas las columnas de inversión)
                capex_total += (
                    self._safe_float(f.get('capex_screen')) + self._safe_float(f.get('capex_civil')) +
                    self._safe_float(f.get('capex_nuc')) + self._safe_float(f.get('capex_crew')) +
                    self._safe_float(f.get('capex_legal')) + self._safe_float(f.get('capex_structure'))
                )
                
                # Sumar OPEX (Todas las columnas mensuales + anuales prorrateadas)
                opex_monthly_total += (
                    self._safe_float(f.get('opex_light')) + self._safe_float(f.get('opex_internet')) +
                    self._safe_float(f.get('opex_rent')) + (self._safe_float(f.get('opex_license_annual')) / 12)
                )

                # Sumar Ventas
                sales_monthly_total += self._safe_float(f.get('revenue_monthly'))

            return {
                "kpis": {
                    "capex": capex_total,
                    "sales_annual": sales_monthly_total * 12,
                    "opex_monthly": opex_monthly_total,
                    "incidents": len(tickets),
                    "active_alerts": 0 # Placeholder conectado a monitor real
                },
                "financials": {
                    "months": ['Promedio'],
                    "sales": [sales_monthly_total],
                    "maintenance": [opex_monthly_total]
                }
            }
        except Exception as e:
            logger.error(f"Error Overview: {e}")
            return None

    # --- DETALLE DE PANTALLA ---
    def get_device_detail(self, device_id):
        try:
            # 1. Finanzas (Fila única con columnas anchas)
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            finance_row = fin_resp.data[0] if fin_resp.data else {}

            # 2. Tickets (Historial)
            tic_resp = self.client.table("tickets").select("*").eq("sitio", device_id).execute()
            tickets = tic_resp.data if tic_resp.data else []

            # 3. Info Técnica
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            device_info = dev_resp.data[0] if dev_resp.data else {}

            # Calcular totales al vuelo sumando columnas
            capex = sum([self._safe_float(finance_row.get(k)) for k in finance_row.keys() if k.startswith('capex_')])
            
            opex_monthly = (
                sum([self._safe_float(finance_row.get(k)) for k in finance_row.keys() if k.startswith('opex_') and 'annual' not in k]) +
                (self._safe_float(finance_row.get('opex_license_annual')) / 12)
            )
            
            revenue = self._safe_float(finance_row.get('revenue_monthly'))
            
            # ROI
            margin = revenue - opex_monthly
            roi = (capex / margin) if margin > 0 else 0

            return {
                "device": device_info,
                "financials": finance_row, # Enviamos todo para llenar inputs
                "totals": {
                    "capex": capex,
                    "opex": opex_monthly,
                    "revenue": revenue,
                    "roi": roi
                },
                "history": {"tickets": tickets},
                "eco": self._calculate_eco_impact()
            }

        except Exception as e:
            logger.error(f"Error Detail {device_id}: {e}")
            # Estructura vacía segura
            return {"device":{}, "financials":{}, "totals":{}, "history":{"tickets":[]}, "eco":{}}

    def save_device_financials(self, payload):
        """Guarda TODA la configuración financiera (UPSERT)"""
        try:
            # Limpiar payload de nulos
            clean_payload = {k: v for k, v in payload.items() if v is not None}
            clean_payload['updated_at'] = datetime.now().isoformat()
            
            # Upsert usando device_id como clave única
            self.client.table("finances").upsert(clean_payload, on_conflict="device_id").execute()
            return True
        except Exception as e:
            logger.error(f"Error Save: {e}")
            return False
            
    # Métodos dummy para evitar errores de importación en monitor.py
    def buffer_metric(self, *args, **kwargs): pass
    def upsert_device_status(self, *args, **kwargs): pass
