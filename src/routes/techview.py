# src/routes/techview.py

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
    
    # --- LÓGICA DE DASHBOARD EJECUTIVO ---
    def get_dashboard_data(self):
        """Obtiene datos consolidados para el dashboard ejecutivo"""
        try:
            if not self.client: return {"overview_data": [], "totals": {}}
            
            # Obtener datos brutos
            devices = self.client.table("devices").select("*").execute().data or []
            finances = self.client.table("finances").select("*").execute().data or []
            
            total_capex = 0
            total_revenue = 0
            total_opex = 0
            online_count = 0
            alert_count = 0
            
            overview_data = [] # Lista detallada para la tabla
            
            # Indexar finanzas para búsqueda rápida
            fin_map = {f['device_id']: f for f in finances}
            
            for dev in devices:
                dev_id = dev.get('device_id')
                fin = fin_map.get(dev_id, {})
                
                # Calcular CAPEX usando los nuevos campos
                d_capex = (
                    self._safe_float(fin.get('cost_pantalla', 0)) +
                    self._safe_float(fin.get('cost_obra_civil', 0)) +
                    self._safe_float(fin.get('cost_estructura', 0)) +
                    self._safe_float(fin.get('cost_medidor_cfe', 0)) +
                    self._safe_float(fin.get('cost_inst_electrica', 0)) +
                    self._safe_float(fin.get('cost_novastar', 0)) +
                    self._safe_float(fin.get('cost_ups', 0)) +
                    self._safe_float(fin.get('cost_nuc', 0)) +
                    self._safe_float(fin.get('cost_pastilla_100a', 0)) +
                    self._safe_float(fin.get('cost_pastilla_20a', 0)) +
                    self._safe_float(fin.get('cost_camara', 0)) +
                    self._safe_float(fin.get('cost_teltonika', 0)) +
                    self._safe_float(fin.get('cost_poe', 0)) +
                    self._safe_float(fin.get('cost_cable_hdmi', 0)) +
                    self._safe_float(fin.get('cost_ont_fibra', 0))
                )
                
                # Ingresos
                d_rev = self._safe_float(fin.get('revenue_monthly', 0))
                
                # OPEX usando los nuevos campos
                d_opex = (
                    self._safe_float(fin.get('renta_predio', 0)) +
                    self._safe_float(fin.get('costo_cfe', 0)) +
                    self._safe_float(fin.get('internet_fibra', 0)) +
                    self._safe_float(fin.get('internet_redundancia', 0)) +
                    self._safe_float(fin.get('licencia_teltonika', 0)) +
                    self._safe_float(fin.get('licencia_teamviewer', 0)) +
                    self._safe_float(fin.get('licencia_cms', 0)) +
                    self._safe_float(fin.get('licencia_hikvision', 0)) +
                    self._safe_float(fin.get('licencia_ups_portal', 0)) +
                    self._safe_float(fin.get('licencia_qtm', 0))
                )
                
                # Agregar costos de mantenimiento
                d_opex += (
                    self._safe_float(fin.get('maint_preventivo_horas', 0)) * 423.07 +
                    self._safe_float(fin.get('maint_correctivo_horas', 0)) * 423.07 +
                    self._safe_float(fin.get('cantidad_titanio', 0)) * 540.00
                )

                d_margin = d_rev - d_opex
                d_roi = (d_capex / d_margin) if d_margin > 0 else 0
                
                # Totales Globales
                total_capex += d_capex
                total_revenue += d_rev
                total_opex += d_opex
                
                if dev.get('status') == 'online': online_count += 1
                if d_margin < 0 or dev.get('status') == 'offline': alert_count += 1
                
                # Datos por fila
                overview_data.append({
                    "device_id": dev_id,
                    "location": fin.get('location', ''),
                    "pc_name": dev.get('pc_name') or dev_id,
                    "status": dev.get('status', 'unknown'),
                    "monthly_revenue": d_rev,
                    "monthly_opex": d_opex,
                    "monthly_margin": d_margin,
                    "capex": d_capex,
                    "roi_months": d_roi
                })

            # Gráfica Histórica Simulada
            months = []
            sales_hist = []
            cost_hist = []
            current_date = datetime.now()
            
            for i in range(5, -1, -1):
                month_label = (current_date - timedelta(days=30*i)).strftime("%b")
                months.append(month_label)
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
                "financials_history": {
                    "months": months,
                    "sales": sales_hist,
                    "costs": cost_hist
                }
            }
            
        except Exception as e:
            logger.error(f"Error dashboard data: {e}")
            return {"totals": {}, "overview_data": []}

    # --- MÉTODOS DE GESTIÓN INDIVIDUAL (TechView Classic) ---
    def get_device_detail(self, device_id):
        try:
            clean_id = clean_device_id(device_id)
            device_data = self._get_device_info(clean_id)
            finance_data = self._get_finance_info(clean_id)
            maintenance_logs = self._get_maintenance_logs(clean_id)
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
            logger.error(f"Error get_device_detail: {e}")
            return self._create_error_response(device_id, str(e))

    def _get_device_info(self, device_id):
        try:
            if not self.client: return {"device_id": device_id, "status": "unknown"}
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            if dev_resp.data: return dev_resp.data[0]
            else: return {"device_id": device_id, "status": "active", "location": device_id}
        except: return {"device_id": device_id, "status": "unknown"}

    def _get_finance_info(self, device_id):
        try:
            if not self.client: return {}
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            return fin_resp.data[0] if fin_resp.data else {}
        except: return {}

    def _get_maintenance_logs(self, device_id):
        try:
            if not self.client: return []
            return self.client.table("maintenance_logs").select("*").eq("device_id", device_id).limit(50).execute().data
        except: return []

    def _calculate_basic_totals(self, finance_data):
        """Calcula totales usando los nuevos campos de instalación"""
        capex = opex = revenue = 0
        
        if finance_data:
            # CAPEX - Campos de instalación
            capex_fields = [
                'cost_pantalla', 'cost_obra_civil', 'cost_estructura',
                'cost_medidor_cfe', 'cost_inst_electrica', 'cost_novastar',
                'cost_ups', 'cost_nuc', 'cost_pastilla_100a', 'cost_pastilla_20a',
                'cost_camara', 'cost_teltonika', 'cost_poe',
                'cost_cable_hdmi', 'cost_ont_fibra'
            ]
            
            for field in capex_fields:
                capex += self._safe_float(finance_data.get(field, 0))
            
            # OPEX - Gastos mensuales
            opex_fields = [
                'renta_predio', 'costo_cfe', 'internet_fibra', 
                'internet_redundancia', 'licencia_teltonika',
                'licencia_teamviewer', 'licencia_cms', 'licencia_hikvision',
                'licencia_ups_portal', 'licencia_qtm'
            ]
            
            for field in opex_fields:
                opex += self._safe_float(finance_data.get(field, 0))
            
            # Mantenimiento
            horas_preventivo = self._safe_float(finance_data.get('maint_preventivo_horas', 0))
            horas_correctivo = self._safe_float(finance_data.get('maint_correctivo_horas', 0))
            cantidad_titanio = self._safe_float(finance_data.get('cantidad_titanio', 0))
            
            opex += (horas_preventivo * 423.07) + (horas_correctivo * 423.07) + (cantidad_titanio * 540.00)
            
            # Ingresos
            revenue = self._safe_float(finance_data.get('revenue_monthly', 0))
        
        margin = revenue - opex
        roi_months = (capex / margin) if margin > 0 else 0
        
        return {
            "capex": capex,
            "opex_monthly": opex,
            "revenue_monthly": revenue,
            "margin_monthly": margin,
            "roi_months": roi_months
        }

    def _calculate_advanced_kpis(self, finance_data, logs, device):
        """Calcula KPIs avanzados con los nuevos campos"""
        try:
            # Calcular costo total actual
            basic_totals = self._calculate_basic_totals(finance_data)
            capex = basic_totals.get('capex', 0)
            monthly_opex = basic_totals.get('opex_monthly', 0)
            
            # Suponer 12 meses de operación para el costo acumulado
            months_operation = 12
            accumulated_opex = monthly_opex * months_operation
            total_current_cost = capex + accumulated_opex
            
            # Calcular score técnico basado en mantenimiento
            maintenance_score = 85  # Base
            if logs:
                recent_logs = [log for log in logs if datetime.fromisoformat(log.get('date', '').replace('Z', '+00:00')) > datetime.now() - timedelta(days=30)]
                if len(recent_logs) > 3:
                    maintenance_score = 60
                elif len(recent_logs) == 0:
                    maintenance_score = 95
            
            # Tasa de reincidencia
            reincidence_rate = 0
            if logs:
                issues_by_type = {}
                for log in logs:
                    issue_type = log.get('issue_type', 'unknown')
                    issues_by_type[issue_type] = issues_by_type.get(issue_type, 0) + 1
                
                if issues_by_type:
                    max_issues = max(issues_by_type.values())
                    total_issues = sum(issues_by_type.values())
                    reincidence_rate = (max_issues / total_issues * 100) if total_issues > 0 else 0
            
            return {
                "technical_score": maintenance_score,
                "reincidence_rate": round(reincidence_rate, 1),
                "health_status": {"status": "OK", "color": "green"} if maintenance_score >= 70 else {"status": "ALERTA", "color": "orange"},
                "total_current_cost": total_current_cost,
                "accumulated_opex": accumulated_opex,
                "months_operation": months_operation,
                "real_maintenance_total": self._calculate_maintenance_total(finance_data),
                "tco_5year": self._calculate_tco_5year(capex, monthly_opex),
                "break_even_months": self._calculate_break_even(capex, basic_totals.get('margin_monthly', 0))
            }
        except Exception as e:
            logger.error(f"Error calculating advanced KPIs: {e}")
            return {
                "technical_score": 85, 
                "reincidence_rate": 0, 
                "health_status": {"status": "OK", "color": "green"},
                "total_current_cost": 0,
                "accumulated_opex": 0,
                "months_operation": 12,
                "real_maintenance_total": 0,
                "tco_5year": 0,
                "break_even_months": 0
            }

    def _calculate_maintenance_total(self, finance_data):
        """Calcula el costo total de mantenimiento"""
        if not finance_data:
            return 0
        
        horas_preventivo = self._safe_float(finance_data.get('maint_preventivo_horas', 0))
        horas_correctivo = self._safe_float(finance_data.get('maint_correctivo_horas', 0))
        cantidad_titanio = self._safe_float(finance_data.get('cantidad_titanio', 0))
        
        return (horas_preventivo * 423.07) + (horas_correctivo * 423.07) + (cantidad_titanio * 540.00)

    def _calculate_tco_5year(self, capex, monthly_opex):
        """Calcula TCO a 5 años"""
        return capex + (monthly_opex * 12 * 5)

    def _calculate_break_even(self, capex, monthly_margin):
        """Calcula meses para punto de equilibrio"""
        if monthly_margin > 0:
            return math.ceil(capex / monthly_margin)
        return 0

    def _calculate_eco_impact(self, totals):
        """Calcula impacto ecológico"""
        # Estimación simple: cada pantalla ahorra energía vs. métodos tradicionales
        kwh_per_month = 500  # kWh ahorrados por mes
        co2_per_kwh = 0.5    # kg CO2 por kWh
        
        months = 12  # Operación de 12 meses
        kwh_saved = kwh_per_month * months
        co2_tons = (kwh_saved * co2_per_kwh) / 1000  # Convertir a toneladas
        
        return {
            "kwh_saved": kwh_saved,
            "co2_tons": round(co2_tons, 2),
            "trees_equivalent": round(co2_tons * 15, 1)  # 15 árboles por tonelada de CO2
        }

    def _get_financial_projections(self, device_id):
        """Proyecciones financieras para los próximos 5 años"""
        try:
            if not self.client: return []
            
            finance_data = self._get_finance_info(device_id)
            basic_totals = self._calculate_basic_totals(finance_data)
            
            monthly_revenue = basic_totals.get('revenue_monthly', 0)
            monthly_opex = basic_totals.get('opex_monthly', 0)
            capex = basic_totals.get('capex', 0)
            
            projections = []
            cumulative_profit = -capex  # Inicio con inversión negativa
            
            for year in range(1, 6):
                annual_revenue = monthly_revenue * 12 * (1.05 ** (year - 1))  # 5% crecimiento anual
                annual_opex = monthly_opex * 12 * (1.03 ** (year - 1))  # 3% inflación anual
                annual_profit = annual_revenue - annual_opex
                cumulative_profit += annual_profit
                
                projections.append({
                    "year": year,
                    "annual_revenue": annual_revenue,
                    "annual_opex": annual_opex,
                    "annual_profit": annual_profit,
                    "cumulative_profit": cumulative_profit,
                    "roi_percentage": (cumulative_profit / capex * 100) if capex > 0 else 0
                })
            
            return projections
        except Exception as e:
            logger.error(f"Error generating projections: {e}")
            return []

    def _generate_summary(self, totals, kpis, device):
        """Genera resumen ejecutivo"""
        margin = totals.get('margin_monthly', 0)
        roi_months = totals.get('roi_months', 0)
        tech_score = kpis.get('technical_score', 0)
        
        financial_health = "EXCELENTE" if margin > 10000 else "BUENA" if margin > 0 else "CRÍTICA"
        overall_rating = 5 if margin > 15000 and roi_months < 24 else 4 if margin > 5000 else 3 if margin > 0 else 2
        
        return {
            "financial_health": financial_health,
            "overall_rating": overall_rating,
            "recommendation": self._generate_recommendation(margin, roi_months, tech_score),
            "key_strengths": self._identify_strengths(margin, roi_months),
            "areas_improvement": self._identify_improvements(margin, roi_months)
        }

    def _generate_recommendation(self, margin, roi_months, tech_score):
        """Genera recomendación basada en datos"""
        if margin < 0:
            return "Revisar costos operativos urgentemente. Considerar renegociación de rentas o reducción de servicios."
        elif roi_months > 36:
            return "ROI demasiado largo. Evaluar incrementar ingresos mediante mejores pautas publicitarias."
        elif tech_score < 70:
            return "Score técnico bajo. Programar mantenimiento preventivo y revisar estado de componentes."
        elif margin > 15000 and roi_months < 18:
            return "Rentabilidad excelente. Considerar expansión o replicar modelo en nuevas ubicaciones."
        else:
            return "Rendimiento estable. Mantener estrategia actual con monitoreo continuo."

    def _identify_strengths(self, margin, roi_months):
        strengths = []
        if margin > 10000:
            strengths.append("Alto margen operativo")
        if roi_months < 24:
            strengths.append("ROI rápido")
        if margin > 0 and roi_months < 36:
            strengths.append("Rentabilidad sostenible")
        return strengths if strengths else ["Sin fortalezas identificadas"]

    def _identify_improvements(self, margin, roi_months):
        improvements = []
        if margin < 5000:
            improvements.append("Optimizar costos operativos")
        if roi_months > 36:
            improvements.append("Incrementar ingresos")
        if margin < 0:
            improvements.append("Revisar modelo de negocio")
        return improvements if improvements else ["Sin áreas críticas de mejora"]

    def _create_error_response(self, device_id, msg):
        return {"error": msg}

    def save_device_financials(self, payload):
        try:
            if not self.client: return False, "Sin conexión DB"
            device_id = payload.get('device_id')
            if not device_id: return False, "Falta Device ID"
            clean_id = clean_device_id(device_id)
            
            # Mapear campos antiguos a nuevos si es necesario
            field_mapping = {
                # Instalación
                'cost_pantalla': 'cost_pantalla',
                'cost_obra_civil': 'cost_obra_civil',
                'cost_estructura': 'cost_estructura',
                'cost_medidor_cfe': 'cost_medidor_cfe',
                'cost_inst_electrica': 'cost_inst_electrica',
                'cost_novastar': 'cost_novastar',
                'cost_ups': 'cost_ups',
                'cost_nuc': 'cost_nuc',
                'cost_pastilla_100a': 'cost_pastilla_100a',
                'cost_pastilla_20a': 'cost_pastilla_20a',
                'cost_camara': 'cost_camara',
                'cost_teltonika': 'cost_teltonika',
                'cost_poe': 'cost_poe',
                'cost_cable_hdmi': 'cost_cable_hdmi',
                'cost_ont_fibra': 'cost_ont_fibra',
                
                # Gastos mensuales
                'renta_predio': 'renta_predio',
                'costo_cfe': 'costo_cfe',
                'internet_fibra': 'internet_fibra',
                'internet_redundancia': 'internet_redundancia',
                'licencia_teltonika': 'licencia_teltonika',
                'licencia_teamviewer': 'licencia_teamviewer',
                'licencia_cms': 'licencia_cms',
                'licencia_hikvision': 'licencia_hikvision',
                'licencia_ups_portal': 'licencia_ups_portal',
                'licencia_qtm': 'licencia_qtm',
                
                # Mantenimiento
                'maint_preventivo_horas': 'maint_preventivo_horas',
                'maint_correctivo_horas': 'maint_correctivo_horas',
                'cantidad_titanio': 'cantidad_titanio',
                
                # Refacciones
                'refaccion_modulo_cantidad': 'refaccion_modulo_cantidad',
                'refaccion_fuente_cantidad': 'refaccion_fuente_cantidad',
                'refaccion_tarjeta_cantidad': 'refaccion_tarjeta_cantidad',
                'refaccion_cable_fat_metros': 'refaccion_cable_fat_metros',
                'refaccion_cable_modulo_cantidad': 'refaccion_cable_modulo_cantidad',
                'refaccion_cable_fuente_cantidad': 'refaccion_cable_fuente_cantidad',
                'refaccion_novastar_cantidad': 'refaccion_novastar_cantidad',
                'refaccion_ups_cantidad': 'refaccion_ups_cantidad',
                'refaccion_nuc_cantidad': 'refaccion_nuc_cantidad',
            }
            
            # Preparar datos para guardar
            data = {"device_id": clean_id, "updated_at": datetime.now().isoformat()}
            
            for key, value in payload.items():
                if key in field_mapping:
                    db_field = field_mapping[key]
                    # Convertir valores numéricos
                    if 'cantidad' in key or 'metros' in key or 'horas' in key:
                        data[db_field] = self._safe_int(value)
                    elif any(x in key for x in ['cost_', 'renta_', 'costo_', 'internet_', 'licencia_']):
                        data[db_field] = self._safe_float(value)
                    else:
                        data[db_field] = value
            
            # Guardar en la base de datos
            self.client.table("finances").upsert(data, on_conflict="device_id").execute()
            
            # Actualizar dispositivo
            self.client.table("devices").upsert({
                "device_id": clean_id, 
                "updated_at": datetime.now().isoformat(),
                "location": payload.get('location', '')
            }, on_conflict="device_id").execute()
            
            return True, "Datos financieros guardados correctamente"
        except Exception as e:
            logger.error(f"Error save: {e}")
            return False, str(e)

# Instanciar Servicio
techview_service = TechViewService()

# --- RUTAS ---

@bp.route('/')
def index():
    """Dashboard Ejecutivo Principal"""
    return render_template('techview_dashboard.html')

@bp.route('/management')
def management():
    """Gestión individual"""
    device_id = request.args.get('device_id', '')
    return render_template('techview.html', device_id=unquote(device_id))

@bp.route('/api/overview')
def api_overview():
    logger.info("📡 Solicitud recibida en /api/overview")
    data = techview_service.get_dashboard_data()
    return jsonify(data)

@bp.route('/api/dashboard')
def api_dashboard():
    return jsonify(techview_service.get_dashboard_data())

@bp.route('/api/device/<path:device_id>')
def api_device(device_id):
    return jsonify(techview_service.get_device_detail(device_id))

@bp.route('/api/save', methods=['POST'])
def api_save():
    success, msg = techview_service.save_device_financials(request.get_json())
    return jsonify({"success": success, "message": msg}), 200 if success else 500

@bp.route('/api/bulk-update', methods=['POST'])
def api_bulk_update():
    """Actualización masiva de datos"""
    try:
        data = request.get_json()
        devices = data.get('devices', [])
        
        results = []
        for device_data in devices:
            success, msg = techview_service.save_device_financials(device_data)
            results.append({
                "device_id": device_data.get('device_id'),
                "success": success,
                "message": msg
            })
        
        return jsonify({
            "success": True,
            "message": f"Actualizados {len([r for r in results if r['success']])} de {len(devices)} dispositivos",
            "results": results
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
