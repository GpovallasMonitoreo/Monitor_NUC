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
                # Fallback para desarrollo local si no hay env vars (Opcional)
                logger.warning("⚠️ Credenciales de Supabase no encontradas en variables de entorno")
                return 
            
            logger.info("Conectando a Supabase para TechView...")
            self.client = create_client(url, key)
            
            # Test de conexión
            try:
                test = self.client.table("finances").select("count", count="exact").limit(1).execute()
                logger.info(f"✅ TechView conectado a Supabase. Finances: {test.count} registros")
            except Exception as e:
                logger.warning(f"TechView conexión test: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error inicializando TechViewService: {e}")
            raise
    
    # Métodos de compatibilidad
    def buffer_metric(self, *args, **kwargs):
        return True
    
    def upsert_device_status(self, device_id, status, location=None):
        try:
            clean_id = clean_device_id(device_id)
            data = {
                "device_id": clean_id,
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
            if location:
                data["location"] = location
            
            self.client.table("devices").upsert(data, on_conflict="device_id").execute()
            return True
        except Exception as e:
            logger.error(f"Error upsert_device_status: {e}")
            return False
    
    def flush_metrics(self):
        return True
    
    # ============================================
    # MÉTODOS PRINCIPALES DE TECHVIEW
    # ============================================
    
    def _safe_float(self, value):
        try:
            if value is None or value == '':
                return 0.0
            return float(value)
        except:
            return 0.0
    
    def _safe_int(self, value):
        try:
            if value is None or value == '':
                return 0
            # Maneja strings como "3.0" convirtiendo primero a float
            return int(float(value))
        except:
            return 0
    
    def get_device_detail(self, device_id):
        """Obtiene TODOS los detalles del dispositivo incluyendo KPIs avanzados"""
        try:
            clean_id = clean_device_id(device_id)
            logger.info(f"🔍 TechView buscando dispositivo: {clean_id}")
            
            # 1. Obtener información básica del dispositivo
            device_data = self._get_device_info(clean_id)
            
            # 2. Obtener información financiera
            finance_data = self._get_finance_info(clean_id)
            
            # 3. Obtener logs de mantenimiento
            maintenance_logs = self._get_maintenance_logs(clean_id)
            
            # 4. Calcular totales básicos
            basic_totals = self._calculate_basic_totals(finance_data)
            
            # 5. Calcular KPIs avanzados
            advanced_kpis = self._calculate_advanced_kpis(finance_data, maintenance_logs, device_data)
            
            # 6. Calcular impacto ecológico
            eco_impact = self._calculate_eco_impact(basic_totals)
            
            # 7. Obtener proyecciones
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
        """Obtiene información del dispositivo"""
        try:
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            if dev_resp.data:
                return dev_resp.data[0]
            else:
                return {
                    "device_id": device_id,
                    "status": "active",
                    "location": device_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
        except:
            return {"device_id": device_id, "status": "unknown"}
    
    def _get_finance_info(self, device_id):
        """Obtiene información financiera completa"""
        try:
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            return fin_resp.data[0] if fin_resp.data else {}
        except:
            return {}
    
    def _get_maintenance_logs(self, device_id):
        """Obtiene logs de mantenimiento"""
        try:
            # Primero intentar con tabla específica
            logs_resp = self.client.table("maintenance_logs").select("*")\
                .eq("device_id", device_id)\
                .order("log_date", desc=True)\
                .limit(50)\
                .execute()
            return logs_resp.data if logs_resp.data else []
        except:
            # Si no existe la tabla, usar tickets como fallback
            try:
                tickets_resp = self.client.table("tickets").select("*")\
                    .eq("sitio", device_id)\
                    .order("created_at", desc=True)\
                    .limit(20)\
                    .execute()
                return tickets_resp.data if tickets_resp.data else []
            except:
                return []
    
    def _calculate_basic_totals(self, finance_data):
        """Calcula totales financieros básicos"""
        capex = opex = revenue = 0
        
        if finance_data:
            # Sumar CAPEX (todo lo que empieza con capex_)
            for key, value in finance_data.items():
                if key.startswith('capex_'):
                    capex += self._safe_float(value)
                elif key.startswith('opex_') and 'annual' not in key:
                    opex += self._safe_float(value)
                elif key == 'opex_license_annual':
                    opex += (self._safe_float(value) / 12)  # Convertir anual a mensual
                elif key == 'revenue_monthly':
                    revenue = self._safe_float(value)
                elif key == 'maint_prev_bimonthly':
                    opex += (self._safe_float(value) / 2)  # Convertir bimestral a mensual
                elif key.startswith('maint_') and not key.endswith(('count', 'size')): # Ignorar contadores
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
        """Calcula KPIs avanzados de rentabilidad"""
        # Totales básicos
        capex = self._safe_float(finance_data.get('capex_total', 0))
        if capex == 0:
            # Calcular capex si no existe
            capex = sum(self._safe_float(finance_data.get(k, 0)) for k in finance_data if k.startswith('capex_'))
        
        monthly_opex = self._calculate_monthly_opex(finance_data)
        monthly_revenue = self._safe_float(finance_data.get('revenue_monthly', 0))
        
        # 1. Costo Total Acumulado
        installation_date = device_data.get('created_at')
        if installation_date:
            try:
                install_dt = datetime.fromisoformat(installation_date.replace('Z', '+00:00'))
                months_operation = max(1, (datetime.now() - install_dt).days // 30)
            except:
                months_operation = 12  # Fallback
        else:
            months_operation = 12
        
        total_current_cost = capex + (monthly_opex * months_operation)
        
        # 2. Rentabilidad Anual Proyectada
        annual_projected_margin = (monthly_revenue - monthly_opex) * 12
        
        # 3. Tasa de Reincidencia (basado en mantenimiento)
        total_maintenance = len(maintenance_logs)
        corrective_maintenance = sum(1 for log in maintenance_logs 
                                    if log.get('log_type') == 'corrective' or 
                                      log.get('estado') in ['abierto', 'pendiente'])
        
        reincidence_rate = (corrective_maintenance / total_maintenance * 100) if total_maintenance > 0 else 0
        
        # 4. Estado Técnico (Scoring)
        technical_score = self._calculate_technical_score(device_data, maintenance_logs, finance_data)
        
        # 5. Análisis por Categoría
        category_analysis = self._analyze_by_category(finance_data)
        
        # 6. Proyección de Vida Útil
        life_projection = self._calculate_life_projection(finance_data, device_data)
        
        return {
            "total_current_cost": round(total_current_cost, 2),
            "months_operation": months_operation,
            "annual_projected_margin": round(annual_projected_margin, 2),
            "reincidence_rate": round(reincidence_rate, 1),
            "technical_score": round(technical_score, 0),
            "health_status": self._get_health_status(technical_score),
            "category_analysis": category_analysis,
            "life_projection": life_projection,
            "recommendations": self._generate_recommendations(
                reincidence_rate, 
                technical_score, 
                finance_data, 
                maintenance_logs
            )
        }
    
    def _calculate_monthly_opex(self, finance_data):
        """Calcula OPEX mensual total"""
        monthly_opex = 0
        
        # OPEX directo
        opex_fields = [k for k in finance_data if k.startswith('opex_')]
        for field in opex_fields:
            value = self._safe_float(finance_data.get(field, 0))
            if 'annual' in field:
                monthly_opex += (value / 12)
            else:
                monthly_opex += value
        
        # Mantenimiento (convertir a mensual)
        maint_fields = [k for k in finance_data if k.startswith('maint_') and not k.endswith(('count', 'size'))]
        for field in maint_fields:
            value = self._safe_float(finance_data.get(field, 0))
            if 'bimonthly' in field:
                monthly_opex += (value / 2)
            else:
                monthly_opex += value
        
        return monthly_opex
    
    def _calculate_technical_score(self, device_data, maintenance_logs, finance_data):
        """Calcula score técnico del dispositivo (0-100)"""
        score = 100  # Base
        
        # 1. Restar por estado del dispositivo
        status = device_data.get('status', '').lower()
        if status in ['offline', 'error', 'inactive']:
            score -= 30
        elif status in ['warning', 'degraded']:
            score -= 15
        
        # 2. Restar por incidentes recientes (últimos 90 días)
        recent_corrective = 0
        ninety_days_ago = datetime.now() - timedelta(days=90)
        
        for log in maintenance_logs:
            log_date = log.get('log_date') or log.get('created_at') or log.get('timestamp')
            if log_date:
                try:
                    log_dt = datetime.fromisoformat(log_date.replace('Z', '+00:00'))
                    if log_dt > ninety_days_ago:
                        log_type = log.get('log_type') or log.get('action', '').lower()
                        if 'corrective' in log_type or 'correctivo' in log_type:
                            recent_corrective += 1
                except:
                    pass
        
        score -= (recent_corrective * 10)
        
        # 3. Restar por falta de mantenimiento preventivo
        last_preventive = None
        for log in maintenance_logs:
            log_type = log.get('log_type') or log.get('action', '').lower()
            if 'preventive' in log_type or 'preventivo' in log_type:
                log_date = log.get('log_date') or log.get('created_at')
                if log_date:
                    try:
                        log_dt = datetime.fromisoformat(log_date.replace('Z', '+00:00'))
                        if not last_preventive or log_dt > last_preventive:
                            last_preventive = log_dt
                    except:
                        pass
        
        if last_preventive:
            days_since_preventive = (datetime.now() - last_preventive).days
            if days_since_preventive > 90:  # Más de 3 meses
                score -= 20
            elif days_since_preventive > 60:  # Más de 2 meses
                score -= 10
        
        # 4. Ajustar por antigüedad (si tenemos fecha de instalación)
        install_date = device_data.get('created_at') or finance_data.get('life_installation_date')
        if install_date:
            try:
                install_dt = datetime.fromisoformat(install_date.replace('Z', '+00:00'))
                months_old = (datetime.now() - install_dt).days / 30
                if months_old > 36:  # Más de 3 años
                    score -= 15
                elif months_old > 24:  # Más de 2 años
                    score -= 8
            except:
                pass
        
        return max(0, min(100, score))
    
    def _analyze_by_category(self, finance_data):
        """Analiza distribución por categoría"""
        categories = {
            "infraestructura": ["capex_screen", "capex_civil", "capex_structure", 
                               "capex_electrical", "capex_meter", "capex_data_install"],
            "electronica": ["capex_nuc", "capex_ups", "capex_sending", "capex_processor",
                           "capex_modem_wifi", "capex_modem_sim", "capex_teltonika", 
                           "capex_hdmi", "capex_camera"],
            "mano_obra": ["capex_crew", "capex_logistics"],
            "legal": ["capex_legal", "capex_first_install", "capex_admin_qtm"],
            "suministros": ["opex_light", "opex_internet", "opex_rent", "opex_soil_use"],
            "software": ["opex_license_annual", "opex_content_scheduling", "opex_srd"],
            "mantenimiento": ["maint_prev_bimonthly", "maint_cleaning_supplies", 
                             "maint_gas", "maint_corr_parts", "maint_corr_labor"]
        }
        
        analysis = {}
        total_capex = 0
        total_opex = 0
        
        for category, fields in categories.items():
            category_total = 0
            for field in fields:
                if field in finance_data:
                    value = self._safe_float(finance_data[field])
                    category_total += value
                    
                    # Clasificar como CAPEX u OPEX
                    if field.startswith('capex_'):
                        total_capex += value
                    elif field.startswith(('opex_', 'maint_')):
                        total_opex += value
            
            analysis[category] = {
                "total": round(category_total, 2),
                "percentage_capex": round((category_total / total_capex * 100), 1) if total_capex > 0 else 0,
                "percentage_opex": round((category_total / total_opex * 100), 1) if total_opex > 0 else 0
            }
        
        return analysis
    
    def _calculate_life_projection(self, finance_data, device_data):
        """Calcula proyección de vida útil"""
        install_date = device_data.get('created_at') or finance_data.get('life_installation_date')
        retirement_date = finance_data.get('life_retirement_date')
        renewal_date = finance_data.get('life_renewal_date')
        
        projection = {
            "estimated_life_years": 5,  # Default
            "months_remaining": 60,
            "next_major_event": None,
            "event_date": None
        }
        
        if install_date:
            try:
                install_dt = datetime.fromisoformat(install_date.replace('Z', '+00:00'))
                months_in_operation = (datetime.now() - install_dt).days // 30
                
                # Si hay fecha de retiro, usar esa
                if retirement_date:
                    try:
                        retirement_dt = datetime.fromisoformat(retirement_date.replace('Z', '+00:00'))
                        months_remaining = max(0, (retirement_dt - datetime.now()).days // 30)
                        projection["next_major_event"] = "Retiro"
                        projection["event_date"] = retirement_date
                    except:
                        months_remaining = max(0, 60 - months_in_operation)
                # Si hay fecha de renovación
                elif renewal_date:
                    try:
                        renewal_dt = datetime.fromisoformat(renewal_date.replace('Z', '+00:00'))
                        months_remaining = max(0, (renewal_dt - datetime.now()).days // 30)
                        projection["next_major_event"] = "Renovación"
                        projection["event_date"] = renewal_date
                    except:
                        months_remaining = max(0, 60 - months_in_operation)
                else:
                    months_remaining = max(0, 60 - months_in_operation)
                
                projection["months_remaining"] = months_remaining
                projection["estimated_life_years"] = round((months_in_operation + months_remaining) / 12, 1)
                
            except:
                pass
        
        return projection
    
    def _calculate_eco_impact(self, totals):
        """Calcula impacto ecológico"""
        # Fórmula: Ahorro vs pantalla tradicional de 450W
        daily_hours = 18
        days_per_year = 365
        watt_saved_per_hour = 300  # 450W tradicional - 150W LED actual
        
        kwh_saved = (watt_saved_per_hour * daily_hours * days_per_year) / 1000
        co2_tons = (kwh_saved * 0.45) / 1000  # 0.45 kg CO2 por kWh
        trees_equivalent = int(co2_tons * 50)  # Cada árbol absorbe ~20kg CO2 al año
        
        # Ahorro económico basado en costo de energía
        energy_cost_per_kwh = 0.15  # USD por kWh (ajustable)
        annual_energy_savings = kwh_saved * energy_cost_per_kwh
        
        return {
            "kwh_saved": round(kwh_saved, 0),
            "co2_tons": round(co2_tons, 2),
            "trees": trees_equivalent,
            "efficiency_gain": "66%",
            "daily_savings": round(kwh_saved / 365, 2),
            "annual_energy_savings": round(annual_energy_savings, 2),
            "equivalent_homes": round(kwh_saved / 10800, 1)  # Consumo anual promedio hogar
        }
    
    def _get_financial_projections(self, device_id):
        """Obtiene proyecciones financieras"""
        try:
            proj_resp = self.client.table("financial_projections")\
                .select("*")\
                .eq("device_id", device_id)\
                .order("projection_date", desc=True)\
                .limit(5)\
                .execute()
            
            if proj_resp.data:
                return proj_resp.data
            else:
                # Generar proyección básica si no existe
                return self._generate_basic_projection(device_id)
        except:
            return self._generate_basic_projection(device_id)
    
    def _generate_basic_projection(self, device_id):
        """Genera proyección básica si no hay datos"""
        # Obtener datos actuales
        finance_data = self._get_finance_info(device_id)
        monthly_revenue = self._safe_float(finance_data.get('revenue_monthly', 0))
        monthly_opex = self._calculate_monthly_opex(finance_data)
        
        # Proyectar 12 meses con crecimiento del 5%
        projections = []
        base_date = datetime.now()
        
        for i in range(1, 13):
            projection_date = (base_date.replace(day=1) + timedelta(days=30*i)).replace(day=1)
            growth_factor = 1 + (0.05 * (i / 12))  # 5% anual
            
            projections.append({
                "projection_date": projection_date.strftime("%Y-%m-%d"),
                "projected_revenue": round(monthly_revenue * growth_factor, 2),
                "projected_opex": round(monthly_opex * 1.02, 2),  # 2% inflación
                "projected_margin": round((monthly_revenue * growth_factor) - (monthly_opex * 1.02), 2),
                "notes": f"Proyección automática mes {i}"
            })
        
        return projections
    
    def _get_health_status(self, score):
        """Determina estado de salud basado en scoring"""
        if score >= 80:
            return {"status": "Excelente", "color": "emerald", "icon": "✅"}
        elif score >= 60:
            return {"status": "Bueno", "color": "blue", "icon": "👍"}
        elif score >= 40:
            return {"status": "Regular", "color": "amber", "icon": "⚠️"}
        else:
            return {"status": "Crítico", "color": "red", "icon": "🚨"}
    
    def _generate_recommendations(self, reincidence_rate, technical_score, finance_data, maintenance_logs):
        """Genera recomendaciones basadas en análisis"""
        recommendations = []
        
        # Análisis de reincidencia
        if reincidence_rate > 30:
            recommendations.append({
                "type": "urgent",
                "message": "Alta tasa de reincidencia (>30%). Considerar renovación tecnológica completa.",
                "action": "Programar auditoría técnica"
            })
        elif reincidence_rate > 15:
            recommendations.append({
                "type": "warning",
                "message": "Tasa de reincidencia moderada. Revisar procedimientos de mantenimiento.",
                "action": "Optimizar mantenimiento preventivo"
            })
        
        # Análisis de estado técnico
        if technical_score < 50:
            recommendations.append({
                "type": "urgent",
                "message": f"Estado técnico crítico ({technical_score}/100). Riesgo de falla inminente.",
                "action": "Intervención técnica prioritaria"
            })
        elif technical_score < 70:
            recommendations.append({
                "type": "warning",
                "message": f"Estado técnico regular ({technical_score}/100). Programar mantenimiento.",
                "action": "Agendar mantenimiento preventivo"
            })
        
        # Análisis de ROI
        roi = self._safe_float(finance_data.get('roi_months', 0))
        if roi > 36:  # Más de 3 años para ROI
            recommendations.append({
                "type": "warning",
                "message": f"ROI muy largo ({roi:.1f} meses). Revisar estrategia de precios.",
                "action": "Revisar modelo de precios"
            })
        
        # Análisis de mantenimiento preventivo
        last_preventive = None
        for log in maintenance_logs:
            if 'preventive' in str(log.get('log_type', '')).lower():
                log_date = log.get('log_date') or log.get('created_at')
                if log_date:
                    try:
                        log_dt = datetime.fromisoformat(log_date.replace('Z', '+00:00'))
                        if not last_preventive or log_dt > last_preventive:
                            last_preventive = log_dt
                    except:
                        pass
        
        if last_preventive:
            days_since = (datetime.now() - last_preventive).days
            if days_since > 90:
                recommendations.append({
                    "type": "warning",
                    "message": f"Mantenimiento preventivo atrasado ({days_since} días).",
                    "action": "Programar mantenimiento preventivo"
                })
        
        # Si no hay recomendaciones críticas
        if not recommendations and technical_score > 80 and reincidence_rate < 10:
            recommendations.append({
                "type": "info",
                "message": "Equipo en excelente estado. Mantener programa actual.",
                "action": "Continuar monitoreo regular"
            })
        
        return recommendations
    
    def _generate_summary(self, totals, advanced_kpis, device_data):
        """Genera resumen ejecutivo"""
        roi_years = totals.get('roi_years', 0)
        health_status = advanced_kpis.get('health_status', {}).get('status', 'Desconocido')
        
        summary = {
            "financial_health": "Excelente" if roi_years < 2 else "Bueno" if roi_years < 4 else "Regular",
            "operational_status": health_status,
            "key_strength": None,
            "key_concern": None,
            "overall_rating": None
        }
        
        # Determinar fortalezas y preocupaciones
        if totals.get('margin_monthly', 0) > 1000:
            summary["key_strength"] = "Alta rentabilidad mensual"
        elif advanced_kpis.get('technical_score', 0) > 80:
            summary["key_strength"] = "Excelente estado técnico"
        
        if advanced_kpis.get('reincidence_rate', 0) > 20:
            summary["key_concern"] = "Alta tasa de incidentes"
        elif roi_years > 5:
            summary["key_concern"] = "ROI demasiado largo"
        
        # Calcular rating general (1-5 estrellas)
        rating_score = 0
        rating_score += 1 if totals.get('margin_monthly', 0) > 0 else 0
        rating_score += 1 if advanced_kpis.get('technical_score', 0) > 70 else 0
        rating_score += 1 if advanced_kpis.get('reincidence_rate', 0) < 15 else 0
        rating_score += 1 if roi_years < 3 else 0
        rating_score += 1 if device_data.get('status') == 'online' else 0
        
        summary["overall_rating"] = rating_score
        
        return summary
    
    def _create_error_response(self, device_id, error_msg):
        """Crea respuesta de error estructurada"""
        return {
            "error": error_msg,
            "device": {"device_id": device_id, "status": "error"},
            "financials": {},
            "maintenance_logs": [],
            "totals": {
                "capex": 0, "opex_monthly": 0, "opex_annual": 0,
                "revenue_monthly": 0, "revenue_annual": 0,
                "margin_monthly": 0, "margin_annual": 0,
                "roi_months": 0, "roi_years": 0
            },
            "advanced_kpis": {
                "total_current_cost": 0,
                "months_operation": 0,
                "annual_projected_margin": 0,
                "reincidence_rate": 0,
                "technical_score": 0,
                "health_status": {"status": "Error", "color": "gray", "icon": "❓"},
                "category_analysis": {},
                "life_projection": {},
                "recommendations": []
            },
            "eco": {
                "kwh_saved": 0, "co2_tons": 0, "trees": 0,
                "efficiency_gain": "0%", "daily_savings": 0,
                "annual_energy_savings": 0, "equivalent_homes": 0
            },
            "projections": [],
            "summary": {
                "financial_health": "Error",
                "operational_status": "Error",
                "key_strength": None,
                "key_concern": "Error en sistema",
                "overall_rating": 0
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def save_device_financials(self, payload):
        """Guardar datos financieros - Versión corregida para enteros"""
        try:
            logger.info(f"💾 TechView guardando datos para: {payload.get('device_id')}")
            
            device_id = payload.get('device_id')
            if not device_id:
                return False, "device_id es requerido"
            
            clean_id = clean_device_id(device_id)
            
            # Preparar datos
            data_to_save = {
                "device_id": clean_id,
                "cost_type": payload.get('cost_type', 'techview'),
                "category": payload.get('category', 'comprehensive'),
                "concept": payload.get('concept', 'techview_save'),
                "updated_at": datetime.now().isoformat()
            }
            
            # Lista completa de campos
            all_fields = [
                # CAPEX
                'capex_screen', 'capex_civil', 'capex_structure', 'capex_electrical',
                'capex_meter', 'capex_data_install', 'capex_transportation',
                'capex_negotiations', 'capex_inventory',
                'capex_nuc', 'capex_ups', 'capex_sending', 'capex_processor',
                'capex_modem_wifi', 'capex_modem_sim', 'capex_teltonika',
                'capex_hdmi', 'capex_camera',
                'capex_crew', 'capex_logistics', 'capex_legal',
                'capex_first_install', 'capex_admin_qtm',
                
                # OPEX
                'opex_light', 'opex_internet', 'opex_internet_sim', 'opex_internet_cable',
                'opex_rent', 'opex_soil_use', 'opex_taxes', 'opex_insurance',
                'opex_license_annual', 'opex_content_scheduling', 'opex_srd',
                
                # Mantenimiento
                'maint_prev_bimonthly', 'maint_cleaning_supplies', 'maint_gas',
                'maint_corr_parts', 'maint_corr_labor', 'maint_corr_gas',
                'maint_visit_count', 'maint_corr_visit_count', 'maint_crew_size',
                
                # Ciclo de Vida
                'life_retirement', 'life_renewal', 'life_special',
                'life_retirement_date', 'life_renewal_date', 'life_installation_date',
                
                # Ventas
                'revenue_monthly'
            ]
            
            # Campos que DEBEN ser enteros
            integer_fields = ['maint_visit_count', 'maint_corr_visit_count', 'maint_crew_size']
            
            # Procesar campos
            total_capex = 0
            total_opex = 0
            
            for field in all_fields:
                if field in payload and payload[field] not in [None, '']:
                    if field in ['revenue_monthly'] or field.startswith(('capex_', 'opex_', 'maint_', 'life_')):
                        try:
                            # CORRECCIÓN AQUÍ: Convertir enteros correctamente
                            if field in integer_fields:
                                value = int(float(payload[field]))
                            else:
                                value = float(payload[field])
                            
                            data_to_save[field] = value
                            
                            # Acumular para totales
                            if field.startswith('capex_'):
                                total_capex += value
                            elif field.startswith(('opex_', 'maint_')):
                                # Excluir contadores de la suma monetaria
                                if field not in integer_fields:
                                    total_opex += value
                                
                        except Exception as e:
                            logger.warning(f"Error convirtiendo campo {field}: {e}")
                            data_to_save[field] = 0.0
                    else:
                        data_to_save[field] = str(payload[field])
            
            # Guardar totales calculados
            data_to_save['capex_total'] = total_capex
            data_to_save['opex_monthly_total'] = total_opex
            
            logger.info(f"📤 TechView datos a guardar: {list(data_to_save.keys())}")
            
            # Asegurar que el dispositivo existe
            try:
                self.client.table("devices").upsert({
                    "device_id": clean_id,
                    "status": "active",
                    "location": clean_id,
                    "updated_at": datetime.now().isoformat()
                }, on_conflict="device_id").execute()
            except Exception as e:
                logger.warning(f"⚠️ TechView no pudo actualizar devices: {e}")
            
            # Guardar en finances
            result = self.client.table("finances").upsert(
                data_to_save, 
                on_conflict="device_id"
            ).execute()
            
            logger.info(f"✅ TechView guardado exitoso para {clean_id}")
            return True, "Datos guardados correctamente"
            
        except Exception as e:
            logger.error(f"❌ TechView error save_device_financials: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"Error: {str(e)}"
    
    def get_financial_overview(self, limit=50):
        """Obtiene overview financiero de todos los dispositivos"""
        try:
            # Obtener todos los dispositivos con finanzas
            response = self.client.table("finances").select("*").limit(limit).execute()
            
            overview_data = []
            totals = {
                "total_capex": 0,
                "total_monthly_revenue": 0,
                "total_monthly_opex": 0,
                "total_monthly_margin": 0,
                "device_count": 0,
                "online_count": 0
            }
            
            for finance in response.data:
                device_id = finance.get('device_id')
                if not device_id:
                    continue
                
                # Calcular métricas para este dispositivo
                monthly_revenue = self._safe_float(finance.get('revenue_monthly', 0))
                monthly_opex = self._calculate_monthly_opex(finance)
                capex = sum(self._safe_float(finance.get(k, 0)) for k in finance if k.startswith('capex_'))
                monthly_margin = monthly_revenue - monthly_opex
                
                overview_data.append({
                    "device_id": device_id,
                    "monthly_revenue": monthly_revenue,
                    "monthly_opex": monthly_opex,
                    "monthly_margin": monthly_margin,
                    "capex": capex,
                    "roi_months": (capex / monthly_margin) if monthly_margin > 0 else 0
                })
                
                # Acumular totals
                totals["total_capex"] += capex
                totals["total_monthly_revenue"] += monthly_revenue
                totals["total_monthly_opex"] += monthly_opex
                totals["total_monthly_margin"] += monthly_margin
                totals["device_count"] += 1
            
            return {
                "overview_data": overview_data,
                "totals": totals,
                "average_roi": (totals["total_capex"] / totals["total_monthly_margin"]) 
                              if totals["total_monthly_margin"] > 0 else 0,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error en get_financial_overview: {e}")
            return {
                "overview_data": [],
                "totals": {
                    "total_capex": 0,
                    "total_monthly_revenue": 0,
                    "total_monthly_opex": 0,
                    "total_monthly_margin": 0,
                    "device_count": 0,
                    "online_count": 0
                },
                "average_roi": 0,
                "timestamp": datetime.now().isoformat()
            }

# Instancia global para TechView
techview_service = None
try:
    techview_service = TechViewService()
    logger.info("✅ TechViewService inicializado")
except Exception as e:
    logger.error(f"❌ No se pudo inicializar TechViewService: {e}")

# ============================================
# RUTAS TECHVIEW
# ============================================

@bp.route('/')
def index():
    return '''
    <html>
    <head>
        <title>TechView - Sistema Financiero</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .stat-card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 1px 5px rgba(0,0,0,0.05); }
            .stat-value { font-size: 24px; font-weight: bold; margin: 5px 0; }
            .stat-label { color: #666; font-size: 14px; }
            .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }
            .btn:hover { background: #0056b3; }
            .btn-success { background: #28a745; }
            .btn-warning { background: #ffc107; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 TechView - Sistema Financiero Completo</h1>
                <p>Sistema de gestión financiera y análisis de rentabilidad de dispositivos</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-label">Estado del Servicio</div>
                    <div class="stat-value" style="color: ''' + ('#28a745' if techview_service else '#dc3545') + '''">
                        ''' + ("✅ CONECTADO" if techview_service else "❌ DESCONECTADO") + '''
                    </div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-label">Última Actualización</div>
                    <div class="stat-value">''' + datetime.now().strftime("%H:%M:%S") + '''</div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <h3>📊 Módulos Principales</h3>
                    <ul style="list-style: none; padding: 0;">
                        <li style="margin: 10px 0;"><a href="/techview/diagnostic" class="btn">🔧 Diagnóstico del Sistema</a></li>
                        <li style="margin: 10px 0;"><a href="/techview/overview" class="btn btn-success">📈 Overview Financiero</a></li>
                        <li style="margin: 10px 0;"><a href="/techview/management?device_id=TEST_DEVICE_123" class="btn">💼 Gestión (Ejemplo)</a></li>
                    </ul>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

@bp.route('/diagnostic')
def diagnostic():
    return render_template('techview_diagnostic.html') # Asumiendo que tienes este template, si no, usa el HTML inline anterior

@bp.route('/overview')
def overview():
    return render_template('techview_overview.html')

@bp.route('/management')
def management():
    device_id = request.args.get('device_id', '')
    if not device_id:
        return jsonify({"error": "device_id requerido"}), 400
    
    device_id = unquote(device_id)
    logger.info(f"📱 TechView cargando gestión para: {device_id}")
    
    return render_template('techview.html', device_id=device_id)

# ============================================
# API ENDPOINTS
# ============================================

@bp.route('/api/test')
def api_test():
    if not techview_service:
        return jsonify({"error": "TechView Service no disponible"}), 503
    
    try:
        finances = techview_service.client.table("finances").select("count", count="exact").execute()
        devices = techview_service.client.table("devices").select("count", count="exact").execute()
        
        return jsonify({
            "status": "success",
            "service": "techview",
            "finances_count": finances.count,
            "devices_count": devices.count,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ TechView API test error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@bp.route('/api/overview')
def api_overview():
    if not techview_service:
        return jsonify({"error": "TechView Service no disponible"}), 503
    
    try:
        overview = techview_service.get_financial_overview(limit=100)
        return jsonify(overview)
    except Exception as e:
        logger.error(f"❌ TechView API overview error: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@bp.route('/api/device/<path:device_id>')
def api_device(device_id):
    if not techview_service:
        return jsonify({"error": "TechView Service no disponible"}), 503
    
    try:
        data = techview_service.get_device_detail(device_id)
        return jsonify(data)
    except Exception as e:
        logger.error(f"❌ TechView API device error: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/api/save', methods=['POST'])
def api_save():
    logger.info("=" * 60)
    logger.info("📤 TECHVIEW API SAVE - INICIO")
    
    if not techview_service:
        logger.error("❌ TechView Service no disponible")
        return jsonify({"error": "TechView Service no disponible"}), 503
    
    try:
        if not request.is_json:
            logger.error("❌ No es JSON")
            return jsonify({"error": "Content-Type debe ser application/json"}), 400
        
        data = request.get_json()
        
        if 'device_id' not in data:
            logger.error("❌ device_id faltante")
            return jsonify({"error": "device_id es requerido"}), 400
        
        success, message = techview_service.save_device_financials(data)
        
        if success:
            return jsonify({
                "success": True,
                "message": message,
                "device_id": data['device_id'],
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "success": False,
                "error": message,
                "device_id": data['device_id'],
                "timestamp": datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logger.error(f"🔥 ERROR CRÍTICO en techview_api_save: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Error crítico: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500
