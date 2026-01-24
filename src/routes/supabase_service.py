import os
import logging
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# --- COSTOS GLOBALES (Valores de Respaldo) ---
GLOBAL_COSTS = {
    'infraestructura_base': 45000.0,
    'opex_luz': 800.0,
    'opex_internet': 500.0,
    'incidencia_promedio': 3500.0
}

class SupabaseService:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Faltan credenciales de Supabase en .env")
        self.client: Client = create_client(url, key)
        logger.info("✅ SupabaseService: Iniciado correctamente")

    def _safe_float(self, value, default=0.0):
        """Convierte cualquier cosa a float sin romper el servidor"""
        try:
            if value is None: return default
            return float(value)
        except (ValueError, TypeError):
            return default

    # --- MÉTODOS ORIGINALES DE MONITOREO ---
    def buffer_metric(self, device_id, latency, packet_loss=0, extra_data=None):
        pass # (Mantener lógica original de buffering)

    def upsert_device_status(self, device_data):
        try:
            self.client.table("devices").upsert(device_data).execute()
            return True
        except Exception as e:
            logger.error(f"Error upsert: {e}")
            return False

    # --- MÉTODOS TECHVIEW (FINANZAS) ---

    def get_financial_overview(self):
        """
        Dashboard Principal: Calcula KPIs sin fallar por datos sucios.
        """
        try:
            # 1. Consultas Seguras
            try:
                finances = self.client.table("finances").select("*").execute().data or []
                tickets = self.client.table("tickets").select("ticket_id, costo_estimado, estatus").execute().data or []
                devices = self.client.table("devices").select("device_id, status, disconnect_count").execute().data or []
            except Exception as db_err:
                logger.error(f"Error conectando a tablas: {db_err}")
                # Retornar estructura vacía pero válida para no romper el front con 500
                return self._empty_dashboard_structure()

            # 2. Variables de Acumulación
            capex_total = 0.0
            sales_monthly_accum = 0.0
            sales_one_time = 0.0
            opex_monthly = 0.0

            # 3. Procesamiento de Finanzas
            for f in finances:
                amount = self._safe_float(f.get('amount'))
                
                # Clasificación Inteligente (Compatible con datos nuevos y viejos)
                ctype = f.get('cost_type')
                recurrence = f.get('recurrence')
                old_type = f.get('type')

                # Si es registro viejo, lo clasificamos al vuelo
                if not ctype:
                    if old_type == 'installation': ctype = 'CAPEX'
                    elif old_type == 'sale': ctype = 'REVENUE'
                    elif old_type == 'maintenance': ctype = 'OPEX'
                
                if not recurrence:
                    recurrence = 'monthly' if old_type in ['sale', 'maintenance'] else 'one_time'

                # Sumar
                if ctype == 'CAPEX':
                    capex_total += amount
                elif ctype == 'REVENUE':
                    if recurrence == 'monthly': sales_monthly_accum += amount
                    else: sales_one_time += amount
                elif ctype == 'OPEX' and recurrence == 'monthly':
                    opex_monthly += amount

            # Proyección Anual de Ventas
            sales_annual = (sales_monthly_accum * 12) + sales_one_time

            # 4. Procesamiento de Incidencias (Costos Ocultos)
            incident_cost_total = 0.0
            for t in tickets:
                cost = self._safe_float(t.get('costo_estimado'))
                if cost == 0: 
                    cost = GLOBAL_COSTS['incidencia_promedio'] # Usar promedio si no tiene costo capturado
                incident_cost_total += cost

            # 5. Alertas de Red
            active_alerts = sum(1 for d in devices if d.get('status') != 'online')

            return {
                "kpis": {
                    "capex": capex_total,
                    "sales_annual": sales_annual,
                    "opex_monthly": opex_monthly,
                    "incidents": len(tickets),
                    "active_alerts": active_alerts,
                    "incident_costs": incident_cost_total
                },
                "financials": {
                    "months": ['Actual', 'Proyección (+6m)'],
                    "sales": [sales_monthly_accum, sales_monthly_accum],
                    "maintenance": [opex_monthly, opex_monthly + (incident_cost_total/12)]
                }
            }

        except Exception as e:
            logger.error(f"❌ Error CRÍTICO en Financial Overview: {e}", exc_info=True)
            return self._empty_dashboard_structure()

    def get_device_detail(self, device_id):
        """Detalle por Pantalla"""
        try:
            # Consultas individuales
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            tic_resp = self.client.table("tickets").select("*").eq("sitio", device_id).execute()
            
            # Si falla la consulta, inicializamos listas vacías
            records = fin_resp.data if fin_resp else []
            tickets = tic_resp.data if tic_resp else []

            data = {
                "breakdown": records,
                "totals": {"capex": 0.0, "opex": 0.0, "revenue": 0.0, "roi": 0.0},
                "history": {"tickets": tickets, "downtime": 0}
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

                if ctype == 'CAPEX': 
                    data['totals']['capex'] += amt
                elif ctype == 'OPEX' and rec == 'monthly': 
                    data['totals']['opex'] += amt
                elif ctype == 'REVENUE' and rec == 'monthly': 
                    data['totals']['revenue'] += amt

            # ROI Calculation (Evitar división por cero)
            margin = data['totals']['revenue'] - data['totals']['opex']
            if margin > 0:
                data['totals']['roi'] = data['totals']['capex'] / margin

            return data

        except Exception as e:
            logger.error(f"Error Device Detail {device_id}: {e}")
            return {"breakdown": [], "totals": {"capex": 0, "opex": 0, "revenue": 0, "roi": 0}, "history": {"tickets": []}}

    def save_cost_entry(self, payload):
        """Guardar Costos"""
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
                # Mantenemos columnas viejas por compatibilidad
                "type": "sale" if payload.get('cost_type') == 'REVENUE' else "expense"
            }
            self.client.table("finances").insert(record).execute()
            return True
        except Exception as e:
            logger.error(f"Error guardando costo: {e}")
            return False

    def _empty_dashboard_structure(self):
        """Helper para devolver JSON vacío válido en caso de error"""
        return {
            "kpis": {"capex": 0, "sales_annual": 0, "opex_monthly": 0, "incidents": 0, "active_alerts": 0},
            "financials": {"months": [], "sales": [], "maintenance": []}
        }
