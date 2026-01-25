import os
import logging
import math
import re
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, render_template
from supabase import create_client, Client
from urllib.parse import unquote

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

bp = Blueprint('techview', __name__, url_prefix='/techview')

def clean_device_id(device_id):
    if not device_id: return ""
    try: device_id = unquote(device_id)
    except: pass
    device_id = device_id.replace('\t', ' ')
    device_id = re.sub(r'[\x00-\x1f\x7f]', '', device_id)
    return ' '.join(device_id.split()).strip()

class TechViewService:
    def __init__(self):
        try:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            if not url or not key:
                logger.warning("⚠️ Credenciales de Supabase no encontradas")
                self.client = None
                return 
            logger.info("Conectando a Supabase para TechView...")
            self.client = create_client(url, key)
        except Exception as e:
            logger.error(f"❌ Error inicializando TechViewService: {e}")
            self.client = None
    
    def _safe_float(self, value):
        try:
            if value is None or value == '': return 0.0
            return float(value)
        except: return 0.0
    
    def _safe_int(self, value):
        try:
            if value is None or value == '': return 0
            return int(float(value))
        except: return 0

    # --- API LOGS & HISTORY (NUEVO: Para guardar desde el modal) ---
    def add_maintenance_log(self, payload):
        try:
            if not self.client: return False, "Sin DB"
            
            # Limpiar datos
            log_entry = {
                "device_id": clean_device_id(payload.get('device_id') or payload.get('pc_name')),
                "pc_name": payload.get('pc_name'),
                "action": payload.get('action'),     # Preventivo / Correctivo
                "what": payload.get('what'),         # Componente
                "description": payload.get('desc'),
                "requested_by": payload.get('req'),
                "executed_by": payload.get('exec'),
                "total_cost": self._safe_float(payload.get('cost', 0)), # Costo manual (opcional)
                "is_solved": payload.get('is_solved', True),
                "timestamp": datetime.now().isoformat()
            }
            
            self.client.table("maintenance_logs").insert(log_entry).execute()
            return True, "Registro agregado"
        except Exception as e:
            logger.error(f"Error guardando log: {e}")
            return False, str(e)

    def get_all_history(self):
        try:
            if not self.client: return []
            return self.client.table("maintenance_logs").select("*").order("timestamp", desc=True).limit(100).execute().data
        except: return []

    # --- LÓGICA DASHBOARD ---
    def get_dashboard_data(self):
        try:
            if not self.client: return {"overview_data": [], "totals": {}}
            devices = self.client.table("devices").select("*").execute().data or []
            finances = self.client.table("finances").select("*").execute().data or []
            
            # Obtener logs para sumar costos reales
            all_logs = self.client.table("maintenance_logs").select("*").execute().data or []
            
            total_capex = 0
            total_revenue = 0
            total_opex = 0
            online_count = 0
            alert_count = 0
            overview_data = []
            
            fin_map = {f['device_id']: f for f in finances}
            
            for dev in devices:
                dev_id = dev.get('device_id')
                fin = fin_map.get(dev_id, {})
                
                # Calcular CAPEX
                d_capex = sum(self._safe_float(v) for k,v in fin.items() if k.startswith('capex_'))
                d_rev = self._safe_float(fin.get('revenue_monthly', 0))
                
                # Calcular OPEX Base
                d_opex_base = 0
                for k,v in fin.items():
                    if k.startswith('opex_') and 'annual' not in k: d_opex_base += self._safe_float(v)
                    if k.startswith('maint_') and 'count' not in k: d_opex_base += self._safe_float(v)
                if 'opex_license_annual' in fin: d_opex_base += (self._safe_float(fin['opex_license_annual']) / 12)

                # Sumar Costos Reales de Bitácora para este dispositivo
                dev_logs = [l for l in all_logs if l.get('device_id') == dev_id]
                real_maint_cost = 0
                for log in dev_logs:
                    # Lógica de Costo Automático
                    cost = self._safe_float(log.get('total_cost', 0))
                    if cost == 0: # Si es 0, buscar costo estándar en finanzas
                        action = str(log.get('action', '')).lower()
                        if 'preventivo' in action:
                            cost = self._safe_float(fin.get('maint_prev_bimonthly', 0)) / 2
                        elif 'correctivo' in action:
                            cost = self._safe_float(fin.get('maint_corr_labor', 0))
                    real_maint_cost += cost
                
                # Si queremos mostrar el costo mensual promedio real, podríamos dividir real_maint_cost / meses
                # Para el margen mensual "actual", usamos el OPEX proyectado. 
                # El "Acumulado" usará el real.
                
                d_margin = d_rev - d_opex_base
                d_roi = (d_capex / d_margin) if d_margin > 0 else 0
                
                total_capex += d_capex
                total_revenue += d_rev
                total_opex += d_opex_base
                
                if dev.get('status') == 'online': online_count += 1
                if d_margin < 0 or dev.get('status') == 'offline': alert_count += 1
                
                overview_data.append({
                    "device_id": dev_id,
                    "pc_name": dev.get('pc_name') or dev_id,
                    "status": dev.get('status', 'unknown'),
                    "monthly_revenue": d_rev,
                    "monthly_opex": d_opex_base,
                    "monthly_margin": d_margin,
                    "capex": d_capex,
                    "roi_months": d_roi
                })

            # Gráfica Histórica
            months, sales_hist, cost_hist = [], [], []
            current_date = datetime.now()
            for i in range(5, -1, -1):
                months.append((current_date - timedelta(days=30*i)).strftime("%b"))
                sales_hist.append(total_revenue * (1 - (i * 0.02))) 
                cost_hist.append(total_opex * (1 + (i * 0.01)))

            return {
                "totals": {
                    "total_capex": total_capex,
                    "total_monthly_revenue": total_revenue,
                    "total_monthly_opex": total_opex,
                    "total_monthly_margin": total_revenue - total_opex,
                    "average_roi": (total_capex / (total_revenue - total_opex)) if (total_revenue - total_opex) > 0 else 0,
                    "device_count": len(devices),
                    "online_count": online_count,
                    "alert_count": alert_count
                },
                "overview_data": overview_data,
                "financials_history": {"months": months, "sales": sales_hist, "costs": cost_hist}
            }
        except Exception as e:
            logger.error(f"Error dashboard: {e}")
            return {"totals": {}, "overview_data": []}

    # --- MÉTODOS INDIVIDUALES ---
    def get_device_detail(self, device_id):
        try:
            clean_id = clean_device_id(device_id)
            device_data = self._get_device_info(clean_id)
            finance_data = self._get_finance_info(clean_id)
            maintenance_logs = self._get_maintenance_logs(clean_id)
            basic_totals = self._calculate_basic_totals(finance_data)
            advanced_kpis = self._calculate_advanced_kpis(finance_data, maintenance_logs, device_data)
            eco_impact = self._calculate_eco_impact(basic_totals)
            
            return {
                "device": device_data,
                "financials": finance_data,
                "maintenance_logs": maintenance_logs,
                "totals": basic_totals,
                "advanced_kpis": advanced_kpis,
                "eco": eco_impact
            }
        except Exception as e:
            return self._create_error_response(device_id, str(e))

    def _get_device_info(self, device_id):
        try:
            if not self.client: return {"device_id": device_id}
            resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            return resp.data[0] if resp.data else {"device_id": device_id, "status": "unknown"}
        except: return {"device_id": device_id}

    def _get_finance_info(self, device_id):
        try:
            if not self.client: return {}
            resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            return resp.data[0] if resp.data else {}
        except: return {}

    def _get_maintenance_logs(self, device_id):
        try:
            if not self.client: return []
            return self.client.table("maintenance_logs").select("*").eq("device_id", device_id).order("timestamp", desc=True).limit(50).execute().data
        except: return []

    def _calculate_basic_totals(self, finance_data):
        capex = opex = revenue = 0
        if finance_data:
            for k, v in finance_data.items():
                if k.startswith('capex_'): capex += self._safe_float(v)
                if k.startswith('opex_') and 'annual' not in k: opex += self._safe_float(v)
                if k == 'revenue_monthly': revenue = self._safe_float(v)
                if k.startswith('maint_') and 'count' not in k: 
                    val = self._safe_float(v)
                    if 'bimonthly' in k: opex += val/2
                    else: opex += val
            if 'opex_license_annual' in finance_data: opex += (self._safe_float(finance_data['opex_license_annual']) / 12)
            
        return {"capex": capex, "opex_monthly": opex, "revenue_monthly": revenue, "margin_monthly": revenue-opex, "roi_months": (capex/(revenue-opex)) if (revenue-opex)>0 else 0}

    def _calculate_advanced_kpis(self, finance_data, maintenance_logs, device_data):
        # 1. Recuperar CAPEX
        capex = sum(self._safe_float(finance_data.get(k, 0)) for k in finance_data if k.startswith('capex_'))
        
        # 2. OPEX Mensual Configurado
        monthly_base_opex = self._calculate_basic_totals(finance_data)['opex_monthly']
        monthly_revenue = self._safe_float(finance_data.get('revenue_monthly', 0))
        
        # 3. Tiempo de vida
        install_date = device_data.get('created_at')
        months_operation = 1
        if install_date:
            try:
                dt = datetime.fromisoformat(str(install_date).replace('Z', '+00:00'))
                months_operation = max(1, (datetime.now(dt.tzinfo) - dt).days // 30)
            except: pass
        
        # 4. LÓGICA DE COSTOS REALES (BITÁCORA AUTOMÁTICA)
        real_maintenance_total = 0
        for log in maintenance_logs:
            # A) Costo explícito en el log
            cost = self._safe_float(log.get('total_cost', 0))
            
            # B) Si es 0, buscar costo automático en la configuración financiera
            if cost == 0:
                action = str(log.get('action', '')).lower()
                if 'preventivo' in action:
                    # Costo bimestral / 2 (asumiendo costo mensual) o costo visita única
                    # Aquí usamos bimonthly / 2 como proxy de costo por evento si es mensual
                    cost = self._safe_float(finance_data.get('maint_prev_bimonthly', 0)) / 2
                elif 'correctivo' in action:
                    cost = self._safe_float(finance_data.get('maint_corr_labor', 0)) + self._safe_float(finance_data.get('maint_corr_parts', 0))
            
            real_maintenance_total += cost

        # Costo Acumulado = (OPEX Base * Meses) + Mantenimientos Reales (Bitácora)
        accumulated_opex = (monthly_base_opex * months_operation) + real_maintenance_total
        total_project_cost = capex + accumulated_opex
        
        return {
            "total_current_cost": round(total_project_cost, 2),
            "accumulated_opex": round(accumulated_opex, 2),
            "real_maintenance_total": round(real_maintenance_total, 2), # Debug
            "technical_score": 85, 
            "reincidence_rate": 0
        }

    def _calculate_eco_impact(self, totals):
        return {"kwh_saved": 1971, "co2_tons": 0.89, "trees": 44}

    def _create_error_response(self, device_id, msg):
        return {"error": msg}

    def save_device_financials(self, payload):
        try:
            if not self.client: return False, "Sin DB"
            device_id = payload.get('device_id')
            clean_id = clean_device_id(device_id)
            data = {"device_id": clean_id, "updated_at": datetime.now().isoformat(), **payload}
            
            # Limpieza de tipos
            for k, v in data.items():
                if k in ['maint_crew_size', 'maint_visit_count', 'maint_corr_visit_count']: data[k] = self._safe_int(v)
                elif 'capex' in k or 'opex' in k or 'revenue' in k: 
                    if 'date' not in k and 'special' not in k: data[k] = self._safe_float(v)
            
            self.client.table("finances").upsert(data, on_conflict="device_id").execute()
            self.client.table("devices").upsert({"device_id": clean_id, "updated_at": datetime.now().isoformat()}, on_conflict="device_id").execute()
            return True, "Guardado"
        except Exception as e:
            return False, str(e)

techview_service = TechViewService()

# --- RUTAS ---
@bp.route('/')
def index(): return render_template('techview_dashboard.html')

@bp.route('/management')
def management(): return render_template('techview.html', device_id=unquote(request.args.get('device_id', '')))

@bp.route('/api/dashboard')
@bp.route('/api/overview')
def api_dashboard(): return jsonify(techview_service.get_dashboard_data())

@bp.route('/api/device/<path:device_id>')
def api_device(device_id): return jsonify(techview_service.get_device_detail(device_id))

@bp.route('/api/save', methods=['POST'])
def api_save():
    success, msg = techview_service.save_device_financials(request.get_json())
    return jsonify({"success": success, "message": msg}), 200 if success else 500

@bp.route('/api/history/add', methods=['POST'])
def api_history_add():
    success, msg = techview_service.add_maintenance_log(request.get_json())
    return jsonify({"success": success, "message": msg}), 200 if success else 500

@bp.route('/api/history/all')
def api_history_all():
    return jsonify(techview_service.get_all_history())
