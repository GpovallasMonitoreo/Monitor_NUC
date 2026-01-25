import os
import logging
import traceback
import re
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, render_template
from supabase import create_client, Client
from urllib.parse import unquote

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Blueprint para TechView
bp = Blueprint('techview', __name__, url_prefix='/techview')

def clean_device_id(device_id):
    """Limpia el device_id"""
    if not device_id:
        return ""
    try:
        device_id = unquote(device_id)
    except:
        pass
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
                return 
            
            logger.info("Conectando a Supabase para TechView...")
            self.client = create_client(url, key)
            
        except Exception as e:
            logger.error(f"❌ Error inicializando TechViewService: {e}")
            raise
    
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
    
    def get_device_detail(self, device_id):
        try:
            clean_id = clean_device_id(device_id)
            logger.info(f"🔍 TechView buscando dispositivo: {clean_id}")
            
            # 1. Obtener datos
            device_data = self._get_device_info(clean_id)
            finance_data = self._get_finance_info(clean_id)
            maintenance_logs = self._get_maintenance_logs(clean_id)
            
            # 2. Cálculos
            basic_totals = self._calculate_basic_totals(finance_data)
            advanced_kpis = self._calculate_advanced_kpis(finance_data, maintenance_logs, device_data)
            eco_impact = self._calculate_eco_impact(basic_totals)
            projections = self._get_financial_projections(clean_id)
            
            return {
                "device": device_data,
                "financials": finance_data,
                "maintenance_logs": maintenance_logs,
                "totals": basic_totals,
                "advanced_kpis": advanced_kpis,
                "eco": eco_impact,
                "projections": projections,
                "summary": self._generate_summary(basic_totals, advanced_kpis, device_data),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ TechView error get_device_detail: {e}")
            return self._create_error_response(device_id, str(e))
    
    def _get_device_info(self, device_id):
        try:
            # Traer sensores y status del Monitor de Latencia
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            if dev_resp.data: return dev_resp.data[0]
            else: return {"device_id": device_id, "status": "active", "location": device_id, "created_at": datetime.now().isoformat()}
        except: return {"device_id": device_id, "status": "unknown"}
    
    def _get_finance_info(self, device_id):
        try:
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            return fin_resp.data[0] if fin_resp.data else {}
        except: return {}
    
    def _get_maintenance_logs(self, device_id):
        try:
            # Asegurar traer el costo real de la bitácora
            logs_resp = self.client.table("maintenance_logs").select("*").eq("device_id", device_id).order("log_date", desc=True).limit(50).execute()
            return logs_resp.data if logs_resp.data else []
        except: return []
    
    def _calculate_basic_totals(self, finance_data):
        capex = opex = revenue = 0
        if finance_data:
            for key, value in finance_data.items():
                if key.startswith('capex_'):
                    capex += self._safe_float(value)
                elif key.startswith('opex_') and 'annual' not in key:
                    opex += self._safe_float(value)
                elif key == 'opex_license_annual':
                    opex += (self._safe_float(value) / 12)
                elif key == 'revenue_monthly':
                    revenue = self._safe_float(value)
                elif key == 'maint_prev_bimonthly':
                    opex += (self._safe_float(value) / 2)
                elif key.startswith('maint_') and not key.endswith(('count', 'size')):
                    opex += self._safe_float(value)
        
        margin = revenue - opex
        roi_months = (capex / margin) if margin > 0 and capex > 0 else 0
        return {
            "capex": round(capex, 2),
            "opex_monthly": round(opex, 2),
            "opex_annual": round(opex * 12, 2),
            "revenue_monthly": round(revenue, 2),
            "revenue_annual": round(revenue * 12, 2),
            "margin_monthly": round(margin, 2),
            "margin_annual": round(margin * 12, 2),
            "roi_months": round(roi_months, 2),
            "roi_years": round(roi_months / 12, 2) if roi_months > 0 else 0
        }
    
    def _calculate_advanced_kpis(self, finance_data, maintenance_logs, device_data):
        # 1. Recuperar CAPEX
        capex = sum(self._safe_float(finance_data.get(k, 0)) for k in finance_data if k.startswith('capex_'))
        
        # 2. Recuperar Flujo Mensual Proyectado (OPEX + Mantenimiento Configurado)
        monthly_burn_rate = self._calculate_monthly_opex(finance_data)
        monthly_revenue = self._safe_float(finance_data.get('revenue_monthly', 0))
        
        # 3. Calcular tiempo de vida
        install_date = device_data.get('created_at') or finance_data.get('life_installation_date')
        months_operation = 1
        if install_date:
            try:
                install_dt = datetime.fromisoformat(str(install_date).replace('Z', '+00:00'))
                days_diff = (datetime.now(install_dt.tzinfo) - install_dt).days
                months_operation = max(1, days_diff // 30)
            except: 
                months_operation = 1
        
        # --- LÓGICA DE COSTOS REALES (BITÁCORA) ---
        # Sumar costos explícitos reportados en la bitácora de mantenimiento del Monitor
        real_maintenance_cost_total = 0
        for log in maintenance_logs:
            # Buscar campo 'cost' o 'total_cost' en el log
            cost = self._safe_float(log.get('cost', 0)) or self._safe_float(log.get('total_cost', 0))
            real_maintenance_cost_total += cost

        # A) Suma de todos los meses (OPEX Proyectado + Mantenimientos Reales Extra)
        # Asumimos que el monthly_burn_rate ya cubre el mantenimiento preventivo básico.
        # Los logs suelen ser correctivos o extras.
        accumulated_opex = (monthly_burn_rate * months_operation) + real_maintenance_cost_total
        
        # B) Cuenta todo con inversión inicial (TCO)
        total_project_cost = capex + accumulated_opex
        # -----------------------------------

        annual_projected_margin = (monthly_revenue - monthly_burn_rate) * 12
        
        # Telemetría del Monitor
        total_maint = len(maintenance_logs)
        disconnects = device_data.get('disconnect_count', 0)
        corrective = sum(1 for log in maintenance_logs if log.get('log_type') == 'corrective')
        
        reincidence = ((corrective + (disconnects/10)) / max(1, total_maint + (months_operation/2))) * 100
        
        technical_score = self._calculate_technical_score(device_data, maintenance_logs, finance_data)
        category_analysis = self._analyze_by_category(finance_data)
        life_projection = self._calculate_life_projection(finance_data, device_data)
        
        return {
            "total_current_cost": round(total_project_cost, 2), # TCO (Capex + Opex + Manto Real)
            "accumulated_opex": round(accumulated_opex, 2),     # Histórico Operativo
            "real_maintenance_total": round(real_maintenance_cost_total, 2), # Desglose solo manto real
            "months_operation": months_operation,
            "annual_projected_margin": round(annual_projected_margin, 2),
            "reincidence_rate": round(reincidence, 1),
            "technical_score": round(technical_score, 0),
            "health_status": self._get_health_status(technical_score),
            "category_analysis": category_analysis,
            "life_projection": life_projection,
            "recommendations": [] 
        }
    
    def _calculate_monthly_opex(self, finance_data):
        monthly_opex = 0
        for k, v in finance_data.items():
            val = self._safe_float(v)
            if k.startswith('opex_'):
                if 'annual' in k: monthly_opex += (val / 12)
                else: monthly_opex += val
            elif k.startswith('maint_') and not k.endswith(('count', 'size')):
                if 'bimonthly' in k: monthly_opex += (val / 2)
                else: monthly_opex += val
        return monthly_opex

    def _calculate_technical_score(self, device_data, maintenance_logs, finance_data):
        score = 100
        status = device_data.get('status', 'unknown')
        if status == 'offline': score -= 30
        elif status == 'warning': score -= 15
        
        disconnects = self._safe_int(device_data.get('disconnect_count', 0))
        if disconnects > 50: score -= 20
        elif disconnects > 10: score -= 5
        
        return max(0, min(100, score))

    def _analyze_by_category(self, finance_data):
        return {} 

    def _calculate_life_projection(self, finance_data, device_data):
        return {"estimated_life_years": 5, "months_remaining": 60}

    def _calculate_eco_impact(self, totals):
        kwh = 1971 
        return {"kwh_saved": kwh, "co2_tons": round(kwh * 0.45 / 1000, 2), "trees": int(kwh * 0.45 / 1000 * 50)}

    def _get_financial_projections(self, device_id):
        return []

    def _generate_summary(self, totals, advanced, device):
        roi = totals.get('roi_years', 0)
        return {
            "financial_health": "Excelente" if roi < 2 else "Regular",
            "operational_status": advanced.get('health_status', {}).get('status', 'OK'),
            "overall_rating": 4
        }

    def _get_health_status(self, score):
        if score >= 80: return {"status": "Excelente", "color": "emerald"}
        return {"status": "Regular", "color": "amber"}

    def _create_error_response(self, device_id, msg):
        return {"error": msg, "device": {"device_id": device_id}, "totals": {}, "financials": {}}

    def save_device_financials(self, payload):
        try:
            device_id = payload.get('device_id')
            if not device_id: return False, "device_id requerido"
            
            clean_id = clean_device_id(device_id)
            data_to_save = {
                "device_id": clean_id,
                "updated_at": datetime.now().isoformat(),
                **payload 
            }
            
            int_fields = ['maint_visit_count', 'maint_corr_visit_count', 'maint_crew_size']
            for f in int_fields:
                if f in data_to_save:
                    data_to_save[f] = self._safe_int(data_to_save[f])
            
            self.client.table("devices").upsert({"device_id": clean_id, "updated_at": datetime.now().isoformat()}, on_conflict="device_id").execute()
            self.client.table("finances").upsert(data_to_save, on_conflict="device_id").execute()
            
            return True, "Guardado correctamente"
        except Exception as e:
            logger.error(f"Error save: {e}")
            return False, str(e)

techview_service = TechViewService()

@bp.route('/management')
def management():
    device_id = request.args.get('device_id', '')
    return render_template('techview.html', device_id=unquote(device_id))

@bp.route('/api/device/<path:device_id>')
def api_device(device_id):
    return jsonify(techview_service.get_device_detail(device_id))

@bp.route('/api/save', methods=['POST'])
def api_save():
    success, msg = techview_service.save_device_financials(request.get_json())
    return jsonify({"success": success, "message": msg, "timestamp": datetime.now().isoformat()}), 200 if success else 500
