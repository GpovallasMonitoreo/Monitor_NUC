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
        try: return float(value) if value else 0.0
        except: return 0.0

    def _calculate_eco_impact(self):
        """Cálculo real basado en consumo promedio vs NUC"""
        # Ahorro: (450W Legacy - 150W NUC) * 18 horas * 365 días / 1000
        kwh_saved = ((450 - 150) * 18 * 365) / 1000
        co2 = (kwh_saved * 0.42) / 1000 # Factor México 0.42kg/kWh
        trees = int((kwh_saved * 0.42) / 22) # 22kg absorción árbol
        return {"kwh_saved": round(kwh_saved, 2), "co2_tons": round(co2, 2), "trees": trees}

    def get_financial_overview(self):
        """Dashboard General: Suma de columnas"""
        try:
            # Traemos todas las filas financieras
            finances = self.client.table("finances").select("*").execute().data or []
            tickets = self.client.table("tickets").select("id").execute().data or [] # Solo conteo
            
            # Inicializar
            capex_total = 0.0
            opex_mensual_total = 0.0
            ventas_mensual_total = 0.0

            for f in finances:
                # SUMAR COLUMNAS CAPEX
                capex_total += (
                    self._safe_float(f.get('capex_screen')) + self._safe_float(f.get('capex_civil')) +
                    self._safe_float(f.get('capex_structure')) + self._safe_float(f.get('capex_electrical')) +
                    self._safe_float(f.get('capex_nuc')) + self._safe_float(f.get('capex_ups')) +
                    self._safe_float(f.get('capex_sending')) + self._safe_float(f.get('capex_crew')) +
                    self._safe_float(f.get('capex_legal')) 
                    # ... sumar resto de columnas CAPEX si se requiere precisión total
                )

                # SUMAR COLUMNAS OPEX
                opex_mensual_total += (
                    self._safe_float(f.get('opex_light')) + self._safe_float(f.get('opex_internet')) +
                    self._safe_float(f.get('opex_rent')) + self._safe_float(f.get('opex_soil_use')) +
                    (self._safe_float(f.get('opex_license_annual')) / 12) # Prorrateo anual
                )

                # SUMAR VENTAS
                ventas_mensual_total += self._safe_float(f.get('revenue_monthly'))

            return {
                "kpis": {
                    "capex": capex_total,
                    "sales_annual": ventas_mensual_total * 12,
                    "opex_monthly": opex_mensual_total,
                    "incidents": len(tickets),
                    "active_alerts": 0 # Se conecta con monitor en endpoint aparte
                },
                "financials": {
                    "months": ['Promedio'],
                    "sales": [ventas_mensual_total],
                    "maintenance": [opex_mensual_total]
                }
            }
        except Exception as e:
            logger.error(f"Error Overview: {e}")
            return None

    def get_device_detail(self, device_id):
        """Obtiene la fila única de finanzas de este dispositivo"""
        try:
            # 1. Finanzas (La fila ancha)
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            finance_row = fin_resp.data[0] if fin_resp.data else {}

            # 2. Tickets (Historial)
            tic_resp = self.client.table("tickets").select("*").eq("sitio", device_id).execute()
            tickets = tic_resp.data if tic_resp.data else []

            # 3. Dispositivo (Info Técnica)
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            device_info = dev_resp.data[0] if dev_resp.data else {}

            # Calcular Totales al vuelo
            capex = sum([
                self._safe_float(finance_row.get(k)) for k in finance_row.keys() if k.startswith('capex_')
            ])
            
            opex = sum([
                self._safe_float(finance_row.get(k)) for k in finance_row.keys() if k.startswith('opex_') and 'annual' not in k
            ])
            # Sumar parte anual prorrateada
            opex += (self._safe_float(finance_row.get('opex_license_annual')) / 12)

            revenue = self._safe_float(finance_row.get('revenue_monthly'))

            margin = revenue - opex
            roi = (capex / margin) if margin > 0 else 0

            return {
                "device": device_info,
                "financials": finance_row, # Enviamos toda la fila para llenar inputs
                "totals": {
                    "capex": capex,
                    "opex": opex,
                    "revenue": revenue,
                    "roi": roi
                },
                "history": {"tickets": tickets},
                "eco": self._calculate_eco_impact()
            }

        except Exception as e:
            logger.error(f"Error Device {device_id}: {e}")
            return {"device":{}, "financials":{}, "totals":{}, "history":{"tickets":[]}, "eco":{}}

    def save_device_financials(self, payload):
        """Guarda la fila completa (UPSERT)"""
        try:
            # Payload ya viene con las claves correctas (capex_screen, etc.)
            # Agregamos fecha actualización
            payload['updated_at'] = datetime.now().isoformat()
            
            # Usamos upsert basado en device_id (Unique Key)
            self.client.table("finances").upsert(payload, on_conflict="device_id").execute()
            return True
        except Exception as e:
            logger.error(f"Error Save: {e}")
            return False
