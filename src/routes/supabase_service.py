import os
import logging
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# COSTOS GLOBALES (Para rellenar huecos si faltan datos específicos)
GLOBAL_COSTS = {
    'infraestructura_base': 45000.0,
    'opex_luz': 800.0,
    'opex_internet': 500.0,
    'incidencia_promedio': 3500.0 # Costo estimado si el ticket no tiene valor
}

class SupabaseService:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Faltan credenciales de Supabase en .env")
        self.client: Client = create_client(url, key)

    def get_financial_overview(self):
        """
        Calcula KPIs globales cruzando Tickets, Dispositivos y Finanzas.
        """
        try:
            # 1. Traer datos (Usando nombres de columnas correctos según tus CSVs)
            # Tickets: Usamos 'ticket_id' y 'costo_estimado'
            tickets = self.client.table("tickets").select("ticket_id, costo_estimado, estatus").execute().data
            
            # Finanzas: Traemos todo para filtrar en Python (más seguro por ahora)
            finances = self.client.table("finances").select("*").execute().data
            
            # Dispositivos: Usamos 'device_id', 'status', 'disconnect_count'
            devices = self.client.table("devices").select("device_id, status, disconnect_count").execute().data

            # 2. Inicializar acumuladores
            capex_total = 0.0
            sales_annual = 0.0
            opex_monthly = 0.0
            
            # 3. Procesar Finanzas con Lógica de Respaldo (Fallback)
            for f in finances:
                amount = float(f.get('amount') or 0)
                
                # Determinar Tipo y Recurrencia (Compatibilidad con datos viejos y nuevos)
                ctype = f.get('cost_type')
                recurrence = f.get('recurrence')
                old_type = f.get('type') # 'installation', 'sale', 'maintenance'

                # Lógica: Si no tiene cost_type (dato viejo), deducirlo
                if not ctype:
                    if old_type == 'installation': ctype = 'CAPEX'
                    elif old_type == 'sale': ctype = 'REVENUE'
                    elif old_type == 'maintenance': ctype = 'OPEX' # O MAINTENANCE
                
                # Lógica: Si no tiene recurrence, deducirlo
                if not recurrence:
                    recurrence = 'monthly' if old_type in ['sale', 'maintenance'] else 'one_time'

                # SUMAR SEGÚN CLASIFICACIÓN
                if ctype == 'CAPEX':
                    capex_total += amount
                
                elif ctype == 'REVENUE':
                    if recurrence == 'monthly':
                        sales_annual += (amount * 12)
                    else:
                        sales_annual += amount
                
                elif ctype in ['OPEX', 'MAINTENANCE'] and recurrence == 'monthly':
                    opex_monthly += amount

            # 4. Procesar Incidencias (Costos Ocultos)
            incident_cost_total = 0.0
            for t in tickets:
                # Si hay costo en el ticket, úsalo. Si no, usa el promedio global.
                cost = t.get('costo_estimado')
                if cost is not None:
                    incident_cost_total += float(cost)
                else:
                    incident_cost_total += GLOBAL_COSTS['incidencia_promedio']

            # Agregamos el costo de incidencias prorrateado al OPEX mensual (opcional)
            # o simplemente lo mostramos como métrica de salud.
            
            # 5. Procesar Estado de Red (Alertas)
            # Consideramos alerta si status no es 'online' o si tiene muchas desconexiones recientes
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
                    # Datos simulados para la gráfica mensual basados en los totales reales
                    "months": ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun'],
                    "sales": [sales_annual/12] * 6, 
                    "maintenance": [opex_monthly + (incident_cost_total/12)] * 6
                }
            }

        except Exception as e:
            logger.error(f"❌ Error CRÍTICO en Financial Overview: {e}", exc_info=True)
            # Retornar estructura vacía segura para no romper el frontend
            return {
                "kpis": {"capex": 0, "sales_annual": 0, "opex_monthly": 0, "incidents": 0, "active_alerts": 0},
                "financials": {"months": [], "sales": [], "maintenance": []}
            }

    def get_device_detail(self, device_id):
        """Detalle financiero específico para TechView"""
        try:
            # 1. Obtener datos filtrados
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            # En tickets buscamos por 'sitio' que suele ser el nombre o ID
            tic_resp = self.client.table("tickets").select("*").eq("sitio", device_id).execute()

            # Estructura base para el frontend
            data = {
                "breakdown": fin_resp.data, # Para llenar los inputs
                "totals": {
                    "capex": 0, 
                    "opex_monthly": 0, 
                    "sales_monthly": 0, 
                    "roi": 0
                },
                "history": {
                    "tickets": tic_resp.data,
                    "downtime": 0
                }
            }

            if dev_resp.data:
                data['history']['downtime'] = dev_resp.data[0].get('disconnect_count', 0)

            # Calcular totales del dispositivo
            for r in fin_resp.data:
                ctype = r.get('cost_type')
                rec = r.get('recurrence')
                amt = float(r.get('amount') or 0)

                # Compatibilidad datos viejos
                if not ctype:
                    old = r.get('type')
                    if old == 'installation': ctype = 'CAPEX'
                    elif old == 'sale': ctype = 'REVENUE'
                    else: ctype = 'OPEX'

                if ctype == 'CAPEX': 
                    data['totals']['capex'] += amt
                elif ctype == 'OPEX' and rec == 'monthly': 
                    data['totals']['opex_monthly'] += amt
                elif ctype == 'REVENUE' and rec == 'monthly': 
                    data['totals']['sales_monthly'] += amt

            # ROI
            margin = data['totals']['sales_monthly'] - data['totals']['opex_monthly']
            if margin > 0:
                data['totals']['roi'] = data['totals']['capex'] / margin

            return data

        except Exception as e:
            logger.error(f"❌ Error Device Detail {device_id}: {e}")
            return None

    def save_cost_entry(self, payload):
        """Guarda datos nuevos desde TechView"""
        try:
            record = {
                "device_id": payload['device_id'],
                "cost_type": payload['cost_type'],
                "category": payload['category'],
                "concept": payload['concept'],
                "amount": float(payload['amount']),
                "recurrence": payload.get('recurrence', 'one_time'),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "created_at": datetime.now().isoformat(),
                # Mantenemos columnas viejas por compatibilidad si es necesario
                "type": "sale" if payload['cost_type'] == 'REVENUE' else "expense"
            }
            self.client.table("finances").insert(record).execute()
            return True
        except Exception as e:
            logger.error(f"Error saving: {e}")
            return False
