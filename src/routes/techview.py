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
            return int(value)
        except: 
            try:
                return int(float(value))
            except:
                return 0
    
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
            import traceback
            logger.error(traceback.format_exc())
            return self._create_error_response(device_id, str(e))
    
    def _get_device_info(self, device_id):
        try:
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            if dev_resp.data: 
                return dev_resp.data[0]
            else: 
                return {
                    "device_id": device_id, 
                    "status": "active", 
                    "location": device_id, 
                    "created_at": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error obteniendo info dispositivo: {e}")
            return {"device_id": device_id, "status": "unknown"}
    
    def _get_finance_info(self, device_id):
        try:
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            return fin_resp.data[0] if fin_resp.data else {}
        except Exception as e:
            logger.error(f"Error obteniendo info financiera: {e}")
            return {}
    
    def _get_maintenance_logs(self, device_id):
        try:
            logs_resp = self.client.table("maintenance_logs").select("*").eq("device_id", device_id).order("log_date", desc=True).limit(50).execute()
            return logs_resp.data if logs_resp.data else []
        except Exception as e:
            logger.error(f"Error obteniendo logs mantenimiento: {e}")
            return []
    
    def _calculate_basic_totals(self, finance_data):
        capex = opex = revenue = 0
        
        if finance_data:
            # Calcular CAPEX total
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
        
        # Cálculos adicionales
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
        try:
            # 1. Recuperar CAPEX
            capex = sum(self._safe_float(finance_data.get(k, 0)) for k in finance_data if k.startswith('capex_'))
            
            # 2. Calcular OPEX mensual
            monthly_opex = self._calculate_monthly_opex(finance_data)
            monthly_revenue = self._safe_float(finance_data.get('revenue_monthly', 0))
            
            # 3. Calcular tiempo de vida
            months_operation = self._calculate_months_operation(device_data, finance_data)
            
            # 4. Costos reales de mantenimiento de bitácora
            real_maintenance_total = 0
            for log in maintenance_logs:
                cost = self._safe_float(log.get('cost', 0)) or self._safe_float(log.get('total_cost', 0))
                real_maintenance_total += cost

            # 5. Costos acumulados históricos
            accumulated_opex = (monthly_opex * months_operation) + real_maintenance_total
            total_project_cost = capex + accumulated_opex
            
            # 6. Cálculos de TCO (Costo Total de Propiedad a 5 años)
            annual_opex = monthly_opex * 12
            five_year_opex = annual_opex * 5
            
            # Costo promedio de mantenimiento por mes
            avg_monthly_maintenance = real_maintenance_total / months_operation if months_operation > 0 else 0
            five_year_maintenance = avg_monthly_maintenance * 12 * 5
            
            tco_5year = capex + five_year_opex + five_year_maintenance
            tco_monthly_equivalent = tco_5year / (5 * 12) if tco_5year > 0 else 0
            
            # 7. Rentabilidad a 5 años
            annual_revenue = monthly_revenue * 12
            five_year_revenue = annual_revenue * 5
            net_profit_5year = five_year_revenue - tco_5year
            
            # 8. Punto de equilibrio
            monthly_margin = monthly_revenue - monthly_opex
            break_even_months = math.ceil(capex / monthly_margin) if monthly_margin > 0 and capex > 0 else 0
            
            # 9. ROI anual
            annual_margin = monthly_margin * 12
            annual_roi = (annual_margin / capex * 100) if capex > 0 else 0
            
            # 10. Margen operativo
            operating_margin = ((monthly_revenue - monthly_opex) / monthly_revenue * 100) if monthly_revenue > 0 else 0
            
            # 11. Proyección anual
            annual_projected_margin = annual_margin
            
            # 12. Calcular tasa de reincidencia
            total_maint = len(maintenance_logs)
            disconnects = device_data.get('disconnect_count', 0)
            corrective = sum(1 for log in maintenance_logs if log.get('log_type') == 'corrective')
            reincidence = ((corrective + (disconnects/10)) / max(1, total_maint + (months_operation/2))) * 100
            
            # 13. Score técnico
            technical_score = self._calculate_technical_score(device_data, maintenance_logs, finance_data)
            
            # 14. Análisis por categoría
            category_analysis = self._analyze_by_category(finance_data)
            
            # 15. Proyección de vida
            life_projection = self._calculate_life_projection(finance_data, device_data)
            
            # 16. Generar recomendaciones
            recommendations = self._generate_recommendations(
                monthly_margin, net_profit_5year, capex, monthly_opex, monthly_revenue
            )
            
            return {
                # Costos acumulados
                "total_current_cost": round(total_project_cost, 2),
                "accumulated_opex": round(accumulated_opex, 2),
                "real_maintenance_total": round(real_maintenance_total, 2),
                "months_operation": months_operation,
                
                # Métricas TCO
                "tco_5year": round(tco_5year, 2),
                "tco_monthly_equivalent": round(tco_monthly_equivalent, 2),
                "five_year_opex": round(five_year_opex, 2),
                "five_year_maintenance": round(five_year_maintenance, 2),
                "net_profit_5year": round(net_profit_5year, 2),
                
                # Métricas financieras
                "annual_projected_margin": round(annual_projected_margin, 2),
                "break_even_months": break_even_months,
                "annual_roi": round(annual_roi, 1),
                "operating_margin": round(operating_margin, 1),
                
                # Métricas operativas
                "reincidence_rate": round(reincidence, 1),
                "technical_score": round(technical_score, 0),
                "health_status": self._get_health_status(technical_score),
                
                # Análisis
                "category_analysis": category_analysis,
                "life_projection": life_projection,
                "recommendations": recommendations
            }
        except Exception as e:
            logger.error(f"Error calculando KPIs avanzados: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._create_default_kpis()
    
    def _calculate_monthly_opex(self, finance_data):
        """Calcula OPEX mensual total incluyendo mantenimiento"""
        monthly_opex = 0
        
        if not finance_data:
            return monthly_opex
            
        for k, v in finance_data.items():
            val = self._safe_float(v)
            
            # Costos OPEX directos
            if k.startswith('opex_'):
                if 'annual' in k: 
                    monthly_opex += (val / 12)
                else: 
                    monthly_opex += val
            
            # Costos de mantenimiento (ya son mensuales o se convierten)
            elif k.startswith('maint_') and not k.endswith(('count', 'size')):
                if 'bimonthly' in k: 
                    monthly_opex += (val / 2)
                else: 
                    monthly_opex += val
        
        return monthly_opex
    
    def _calculate_months_operation(self, device_data, finance_data):
        """Calcula meses de operación basado en fecha de instalación"""
        try:
            install_date = device_data.get('created_at') or finance_data.get('life_installation_date')
            
            if install_date:
                # Limpiar y convertir fecha
                install_str = str(install_date)
                if 'Z' in install_str:
                    install_str = install_str.replace('Z', '+00:00')
                
                install_dt = datetime.fromisoformat(install_str)
                
                # Calcular diferencia en días
                now = datetime.now(install_dt.tzinfo) if install_dt.tzinfo else datetime.now()
                days_diff = (now - install_dt).days
                
                # Convertir a meses (mínimo 1)
                return max(1, days_diff // 30)
        except Exception as e:
            logger.error(f"Error calculando meses operación: {e}")
        
        # Valor por defecto
        return 1
    
    def _calculate_technical_score(self, device_data, maintenance_logs, finance_data):
        """Calcula score técnico basado en múltiples factores"""
        score = 100
        
        try:
            # 1. Estado del dispositivo
            status = device_data.get('status', 'unknown')
            if status == 'offline': 
                score -= 40
            elif status == 'warning': 
                score -= 20
            elif status == 'online': 
                score += 10
            
            # 2. Conectividad
            disconnects = self._safe_int(device_data.get('disconnect_count', 0))
            if disconnects > 100: 
                score -= 30
            elif disconnects > 50: 
                score -= 20
            elif disconnects > 10: 
                score -= 10
            elif disconnects == 0: 
                score += 5
            
            # 3. Mantenimiento reciente
            if maintenance_logs:
                last_log_date = maintenance_logs[0].get('log_date')
                if last_log_date:
                    try:
                        last_log_str = str(last_log_date)
                        if 'Z' in last_log_str:
                            last_log_str = last_log_str.replace('Z', '+00:00')
                        
                        last_log = datetime.fromisoformat(last_log_str)
                        days_since_last = (datetime.now() - last_log).days
                        
                        if days_since_last > 90:
                            score -= 15  # Sin mantenimiento en 3 meses
                        elif days_since_last < 30:
                            score += 10  # Mantenimiento reciente
                    except:
                        pass
                
                # 4. Proporción mantenimiento correctivo vs preventivo
                total_logs = len(maintenance_logs)
                corrective_logs = sum(1 for log in maintenance_logs if log.get('log_type') == 'corrective')
                
                if total_logs > 0:
                    corrective_ratio = corrective_logs / total_logs
                    if corrective_ratio > 0.7:
                        score -= 25  # Mucho mantenimiento correctivo
                    elif corrective_ratio < 0.3:
                        score += 15  # Mayormente preventivo
            
            # 5. Datos financieros completos
            if finance_data:
                required_fields = ['revenue_monthly', 'opex_light', 'opex_rent']
                missing_fields = sum(1 for field in required_fields if not finance_data.get(field))
                
                if missing_fields == 0:
                    score += 10
                elif missing_fields == len(required_fields):
                    score -= 20
        except Exception as e:
            logger.error(f"Error calculando score técnico: {e}")
        
        # Asegurar límites
        return max(0, min(100, score))
    
    def _analyze_by_category(self, finance_data):
        """Analiza costos por categoría"""
        categories = {
            'infrastructure': 0,
            'electronics': 0,
            'labor': 0,
            'operational': 0,
            'maintenance': 0
        }
        
        if not finance_data:
            return categories
        
        try:
            # CAPEX - Infraestructura
            infra_keys = ['screen', 'civil', 'structure', 'electrical', 'meter', 'data_install']
            for key in infra_keys:
                categories['infrastructure'] += self._safe_float(finance_data.get(f'capex_{key}', 0))
            
            # CAPEX - Electrónica
            electronic_keys = ['nuc', 'ups', 'sending', 'processor', 'modem_wifi', 'modem_sim', 'teltonika', 'hdmi', 'camera']
            for key in electronic_keys:
                categories['electronics'] += self._safe_float(finance_data.get(f'capex_{key}', 0))
            
            # CAPEX - Mano de obra
            labor_keys = ['crew', 'logistics', 'transportation', 'legal', 'negotiations', 'admin_qtm', 'inventory', 'first_install']
            for key in labor_keys:
                categories['labor'] += self._safe_float(finance_data.get(f'capex_{key}', 0))
            
            # OPEX - Operacional
            opex_keys = ['light', 'internet', 'internet_sim', 'internet_cable', 'rent', 'soil_use', 'taxes', 'insurance', 'srd']
            for key in opex_keys:
                categories['operational'] += self._safe_float(finance_data.get(f'opex_{key}', 0))
            
            # Licencia anual (convertir a mensual para análisis)
            if 'opex_license_annual' in finance_data:
                categories['operational'] += (self._safe_float(finance_data['opex_license_annual']) / 12)
            
            # Mantenimiento
            maint_keys = ['prev_bimonthly', 'cleaning_supplies', 'gas', 'corr_labor', 'corr_parts', 'corr_gas']
            for key in maint_keys:
                val = self._safe_float(finance_data.get(f'maint_{key}', 0))
                if 'bimonthly' in key:
                    categories['maintenance'] += (val / 2)
                else:
                    categories['maintenance'] += val
            
            # Redondear valores
            for category in categories:
                categories[category] = round(categories[category], 2)
        except Exception as e:
            logger.error(f"Error analizando categorías: {e}")
        
        return categories
    
    def _calculate_life_projection(self, finance_data, device_data):
        """Calcula proyección de vida útil del activo"""
        try:
            # Fecha de instalación
            install_date = device_data.get('created_at') or finance_data.get('life_installation_date')
            
            # Fecha de retiro o renovación
            retirement_date = finance_data.get('life_retirement_date')
            renewal_date = finance_data.get('life_renewal_date')
            
            # Calcular meses restantes
            months_remaining = 60  # Por defecto 5 años
            
            if install_date:
                install_str = str(install_date)
                if 'Z' in install_str:
                    install_str = install_str.replace('Z', '+00:00')
                
                install_dt = datetime.fromisoformat(install_str)
                now = datetime.now(install_dt.tzinfo) if install_dt.tzinfo else datetime.now()
                
                # Si hay fecha de retiro, calcular meses hasta esa fecha
                if retirement_date:
                    try:
                        retire_str = str(retirement_date)
                        if 'Z' in retire_str:
                            retire_str = retire_str.replace('Z', '+00:00')
                        
                        retire_dt = datetime.fromisoformat(retire_str)
                        months_remaining = max(0, ((retire_dt - now).days // 30))
                    except:
                        pass
                
                # Si hay fecha de renovación, ajustar
                elif renewal_date:
                    try:
                        renew_str = str(renewal_date)
                        if 'Z' in renew_str:
                            renew_str = renew_str.replace('Z', '+00:00')
                        
                        renew_dt = datetime.fromisoformat(renew_str)
                        months_remaining = max(0, ((renew_dt - now).days // 30))
                    except:
                        pass
                
                # Calcular meses desde instalación
                months_operated = max(0, ((now - install_dt).days // 30))
                
                # Vida útil estimada (por defecto 8 años = 96 meses)
                estimated_life_months = 96
                
                # Ajustar según tipo de pantalla y ubicación
                if device_data.get('location'):
                    location = device_data['location'].lower()
                    if 'exterior' in location or 'outdoor' in location:
                        estimated_life_months = 72  # 6 años para exterior
                    elif 'interior' in location or 'indoor' in location:
                        estimated_life_months = 120  # 10 años para interior
                
                # Calcular meses restantes basados en vida útil
                months_remaining = max(0, estimated_life_months - months_operated)
                
        except Exception as e:
            logger.error(f"Error calculando proyección vida: {e}")
            months_remaining = 60
        
        return {
            "estimated_life_years": round(months_remaining / 12, 1),
            "months_remaining": months_remaining,
            "estimated_life_months": 96,
            "retirement_date": retirement_date,
            "renewal_date": renewal_date
        }
    
    def _generate_recommendations(self, monthly_margin, net_profit_5year, capex, monthly_opex, monthly_revenue):
        """Genera recomendaciones basadas en métricas financieras"""
        recommendations = []
        
        try:
            # Análisis de margen mensual
            if monthly_margin < 0:
                recommendations.append({
                    "type": "critical",
                    "title": "Margen Negativo",
                    "description": "El dispositivo opera con pérdidas mensuales. Revisar costos operativos urgentemente.",
                    "action": "Reducir OPEX o aumentar ingresos"
                })
            elif monthly_margin < (monthly_revenue * 0.1) and monthly_revenue > 0:  # Menos del 10% de margen
                recommendations.append({
                    "type": "warning",
                    "title": "Margen Bajo",
                    "description": f"Margen operativo del {((monthly_margin/monthly_revenue)*100):.1f}%. Considerar optimización.",
                    "action": "Analizar costos fijos y variables"
                })
            else:
                if monthly_revenue > 0:
                    recommendations.append({
                        "type": "success",
                        "title": "Margen Saludable",
                        "description": f"Margen operativo del {((monthly_margin/monthly_revenue)*100):.1f}%. Mantener operación.",
                        "action": "Monitorear tendencias"
                    })
            
            # Análisis de rentabilidad a 5 años
            if net_profit_5year < 0:
                recommendations.append({
                    "type": "critical",
                    "title": "Rentabilidad Negativa a 5 años",
                    "description": "Proyección indica pérdidas a largo plazo.",
                    "action": "Reevaluar inversión o estrategia comercial"
                })
            elif capex > 0 and net_profit_5year < capex:  # ROI menor al 100% en 5 años
                recommendations.append({
                    "type": "warning",
                    "title": "ROI Bajo a Largo Plazo",
                    "description": f"Retorno estimado: {((net_profit_5year/capex)*100):.1f}% en 5 años.",
                    "action": "Buscar eficiencias operativas"
                })
            elif capex > 0:
                recommendations.append({
                    "type": "success",
                    "title": "Excelente Rentabilidad Futura",
                    "description": f"ROI proyectado: {((net_profit_5year/capex)*100):.1f}% en 5 años.",
                    "action": "Expandir modelo a ubicaciones similares"
                })
            
            # Análisis de estructura de costos
            if monthly_revenue > 0 and monthly_opex > monthly_revenue * 0.7:  # OPEX mayor al 70% de ingresos
                recommendations.append({
                    "type": "warning",
                    "title": "Estructura de Costos Pesada",
                    "description": "Los costos operativos representan más del 70% de los ingresos.",
                    "action": "Optimizar costos fijos y renegociar contratos"
                })
            
            # Recomendación general basada en múltiples factores
            if len(recommendations) >= 2:
                success_count = sum(1 for r in recommendations if r["type"] == "success")
                if success_count >= 2:
                    recommendations.append({
                        "type": "success",
                        "title": "Activo Altamente Rentable",
                        "description": "Excelente desempeño tanto a corto como largo plazo.",
                        "action": "Considerar replicar este modelo en otras ubicaciones"
                    })
        except Exception as e:
            logger.error(f"Error generando recomendaciones: {e}")
        
        return recommendations
    
    def _get_health_status(self, score):
        """Determina estado de salud basado en score"""
        if score >= 85:
            return {"status": "Excelente", "color": "emerald", "level": 1}
        elif score >= 70:
            return {"status": "Bueno", "color": "green", "level": 2}
        elif score >= 50:
            return {"status": "Regular", "color": "yellow", "level": 3}
        elif score >= 30:
            return {"status": "Crítico", "color": "orange", "level": 4}
        else:
            return {"status": "Alerta", "color": "red", "level": 5}
    
    def _calculate_eco_impact(self, totals):
        """Calcula impacto ecológico"""
        kwh_saved = 1971  # Valor base
        co2_tons = round(kwh_saved * 0.45 / 1000, 2)
        trees = int(co2_tons * 50)
        
        return {
            "kwh_saved": kwh_saved,
            "co2_tons": co2_tons,
            "trees": trees,
            "equivalent_cars": round(co2_tons / 4.6, 1)
        }
    
    def _get_financial_projections(self, device_id):
        """Obtiene proyecciones financieras históricas"""
        try:
            # Buscar historial de cambios financieros
            proj_resp = self.client.table("finance_history").select("*").eq("device_id", device_id).order("created_at", desc=True).limit(12).execute()
            
            if proj_resp.data:
                projections = []
                for record in proj_resp.data:
                    projections.append({
                        "date": record.get("created_at"),
                        "revenue": self._safe_float(record.get("revenue_monthly", 0)),
                        "opex": self._safe_float(record.get("opex_monthly", 0)),
                        "margin": self._safe_float(record.get("margin_monthly", 0))
                    })
                return projections
        except Exception as e:
            logger.error(f"Error obteniendo proyecciones: {e}")
        
        # Datos de ejemplo si no hay historial
        return []
    
    def _generate_summary(self, totals, advanced, device):
        """Genera resumen ejecutivo"""
        try:
            roi_years = totals.get('roi_years', 0)
            net_profit_5year = advanced.get('net_profit_5year', 0)
            technical_score = advanced.get('technical_score', 0)
            capex = totals.get('capex', 0)
            
            # Evaluación financiera
            if roi_years <= 2 and net_profit_5year > capex * 2 and capex > 0:
                financial_health = "Excelente"
                financial_score = 5
            elif roi_years <= 3 and net_profit_5year > capex and capex > 0:
                financial_health = "Bueno"
                financial_score = 4
            elif roi_years <= 5:
                financial_health = "Aceptable"
                financial_score = 3
            elif roi_years > 5:
                financial_health = "Limitado"
                financial_score = 2
            else:
                financial_health = "Crítico"
                financial_score = 1
            
            # Estado operativo
            health_status = advanced.get('health_status', {}).get('status', 'Desconocido')
            
            # Rating general (1-5 estrellas)
            overall_score = (financial_score + (technical_score / 20)) / 2
            overall_rating = min(5, max(1, round(overall_score)))
            
            return {
                "financial_health": financial_health,
                "financial_score": financial_score,
                "operational_status": health_status,
                "overall_rating": overall_rating,
                "key_strengths": self._identify_strengths(totals, advanced),
                "key_risks": self._identify_risks(totals, advanced)
            }
        except Exception as e:
            logger.error(f"Error generando summary: {e}")
            return {
                "financial_health": "Error",
                "operational_status": "Desconocido",
                "overall_rating": 0
            }
    
    def _identify_strengths(self, totals, advanced):
        """Identifica fortalezas del activo"""
        strengths = []
        
        try:
            monthly_revenue = totals.get('revenue_monthly', 0)
            monthly_margin = totals.get('margin_monthly', 0)
            
            if monthly_revenue > 0 and monthly_margin > monthly_revenue * 0.3:
                strengths.append("Alto margen operativo")
            
            if advanced.get('break_even_months', 0) < 24 and advanced.get('break_even_months', 0) > 0:
                strengths.append("Rápido retorno de inversión")
            
            if advanced.get('reincidence_rate', 0) < 10:
                strengths.append("Baja tasa de incidencias")
            
            if advanced.get('technical_score', 0) >= 80:
                strengths.append("Excelente salud técnica")
            
            if totals.get('roi_years', 0) < 3:
                strengths.append("ROI atractivo")
        except Exception as e:
            logger.error(f"Error identificando fortalezas: {e}")
        
        return strengths
    
    def _identify_risks(self, totals, advanced):
        """Identifica riesgos del activo"""
        risks = []
        
        try:
            if totals.get('margin_monthly', 0) < 0:
                risks.append("Pérdidas operativas mensuales")
            
            if advanced.get('net_profit_5year', 0) < 0:
                risks.append("Rentabilidad negativa a largo plazo")
            
            if advanced.get('reincidence_rate', 0) > 30:
                risks.append("Alta tasa de fallas técnicas")
            
            if advanced.get('technical_score', 0) < 50:
                risks.append("Salud técnica crítica")
            
            monthly_revenue = totals.get('revenue_monthly', 0)
            monthly_opex = totals.get('opex_monthly', 0)
            
            if monthly_revenue > 0 and monthly_opex > monthly_revenue * 0.8:
                risks.append("Costos operativos muy elevados")
        except Exception as e:
            logger.error(f"Error identificando riesgos: {e}")
        
        return risks
    
    def _create_default_kpis(self):
        """Crea KPIs por defecto en caso de error"""
        return {
            "total_current_cost": 0,
            "accumulated_opex": 0,
            "real_maintenance_total": 0,
            "months_operation": 1,
            "tco_5year": 0,
            "tco_monthly_equivalent": 0,
            "five_year_opex": 0,
            "five_year_maintenance": 0,
            "net_profit_5year": 0,
            "annual_projected_margin": 0,
            "break_even_months": 0,
            "annual_roi": 0,
            "operating_margin": 0,
            "reincidence_rate": 0,
            "technical_score": 0,
            "health_status": self._get_health_status(0),
            "category_analysis": {},
            "life_projection": {"estimated_life_years": 5, "months_remaining": 60},
            "recommendations": []
        }
    
    def _create_error_response(self, device_id, msg):
        """Crea respuesta de error estructurada"""
        return {
            "error": msg,
            "device": {"device_id": device_id},
            "totals": {
                "capex": 0,
                "opex_monthly": 0,
                "revenue_monthly": 0,
                "margin_monthly": 0,
                "roi_months": 0,
                "roi_years": 0
            },
            "financials": {},
            "advanced_kpis": self._create_default_kpis(),
            "summary": {
                "financial_health": "Error",
                "operational_status": "Desconocido",
                "overall_rating": 0
            }
        }
    
    def save_device_financials(self, payload):
        """Guarda datos financieros del dispositivo - VERSIÓN SIMPLIFICADA Y CORREGIDA"""
        try:
            device_id = payload.get('device_id')
            if not device_id: 
                return False, "device_id requerido"
            
            clean_id = clean_device_id(device_id)
            logger.info(f"💾 Guardando datos financieros para: {clean_id}")
            
            # Preparar datos básicos para guardar
            data_to_save = {
                "device_id": clean_id,
                "updated_at": datetime.now().isoformat()
            }
            
            # Procesar todos los campos del payload
            for key, value in payload.items():
                if key == 'device_id' or key == 'cost_type' or key == 'category':
                    continue  # Saltar campos meta
                
                # Procesar valores
                if value is None or value == '':
                    continue
                
                # Determinar tipo de campo
                if key in ['maint_crew_size', 'maint_visit_count', 'maint_corr_visit_count']:
                    # Campos enteros
                    try:
                        data_to_save[key] = int(value)
                    except:
                        data_to_save[key] = 0
                elif any(x in key for x in ['capex_', 'opex_', 'maint_', 'revenue_', 'life_']):
                    # Campos numéricos
                    try:
                        data_to_save[key] = float(value)
                    except:
                        data_to_save[key] = 0.0
                else:
                    # Campos de texto/fecha
                    data_to_save[key] = value
            
            logger.info(f"📊 Datos a guardar: {list(data_to_save.keys())}")
            
            # INTENTAR GUARDAR - Versión más simple y robusta
            try:
                # Verificar si ya existe un registro
                existing = self.client.table("finances").select("device_id").eq("device_id", clean_id).execute()
                
                if existing.data:
                    # Actualizar registro existente
                    update_result = self.client.table("finances").update(data_to_save).eq("device_id", clean_id).execute()
                    logger.info(f"✅ Registro actualizado para {clean_id}")
                else:
                    # Crear nuevo registro
                    insert_result = self.client.table("finances").insert(data_to_save).execute()
                    logger.info(f"✅ Nuevo registro creado para {clean_id}")
                
                # También actualizar/crear en devices para mantener consistencia
                try:
                    self.client.table("devices").upsert({
                        "device_id": clean_id,
                        "updated_at": datetime.now().isoformat()
                    }, on_conflict="device_id").execute()
                except Exception as dev_e:
                    logger.warning(f"⚠️ No se pudo actualizar tabla devices: {dev_e}")
                
                return True, "Datos financieros guardados correctamente"
                
            except Exception as db_error:
                logger.error(f"❌ Error de base de datos: {db_error}")
                # Intentar método alternativo
                try:
                    # Usar upsert directo
                    upsert_result = self.client.table("finances").upsert(data_to_save, on_conflict="device_id").execute()
                    logger.info(f"✅ Upsert exitoso para {clean_id}")
                    return True, "Datos financieros guardados correctamente (upsert)"
                except Exception as upsert_error:
                    logger.error(f"❌ Error en upsert: {upsert_error}")
                    return False, f"Error de base de datos: {str(upsert_error)}"
                    
        except Exception as e:
            logger.error(f"❌ Error general guardando datos: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, f"Error al guardar: {str(e)}"
    
    def get_inventory(self):
        """Obtiene todos los dispositivos para el dashboard"""
        try:
            devices_resp = self.client.table("devices").select("*").execute()
            return devices_resp.data if devices_resp.data else []
        except Exception as e:
            logger.error(f"Error obteniendo inventario: {e}")
            return []
    
    def get_dashboard_data(self):
        """Obtiene datos para el dashboard principal"""
        try:
            # Obtener todos los dispositivos
            devices = self.get_inventory()
            
            # Obtener datos financieros agregados
            finances_resp = self.client.table("finances").select("*").execute()
            finances = finances_resp.data if finances_resp.data else []
            
            # Calcular KPIs agregados
            total_capex = 0
            total_monthly_revenue = 0
            total_monthly_opex = 0
            online_count = 0
            offline_count = 0
            
            for device in devices:
                # Encontrar datos financieros para este dispositivo
                device_finances = next((f for f in finances if f.get('device_id') == device.get('device_id')), {})
                
                # Sumar CAPEX
                for key, value in device_finances.items():
                    if key.startswith('capex_'):
                        total_capex += self._safe_float(value)
                
                # Sumar ingresos y gastos
                total_monthly_revenue += self._safe_float(device_finances.get('revenue_monthly', 0))
                
                # Calcular OPEX mensual para este dispositivo
                device_monthly_opex = 0
                for key, value in device_finances.items():
                    if key.startswith('opex_') and 'annual' not in key:
                        device_monthly_opex += self._safe_float(value)
                    elif key == 'opex_license_annual':
                        device_monthly_opex += (self._safe_float(value) / 12)
                    elif key == 'maint_prev_bimonthly':
                        device_monthly_opex += (self._safe_float(value) / 2)
                    elif key.startswith('maint_') and not key.endswith(('count', 'size')):
                        device_monthly_opex += self._safe_float(value)
                
                total_monthly_opex += device_monthly_opex
                
                # Contar estados
                if device.get('status') == 'online':
                    online_count += 1
                else:
                    offline_count += 1
            
            # Datos para gráfico (últimos 6 meses)
            months = []
            sales_data = []
            cost_data = []
            
            current_date = datetime.now()
            for i in range(6, 0, -1):
                month_date = current_date - timedelta(days=30*i)
                month_name = month_date.strftime('%b')
                months.append(month_name)
                
                # Datos de ejemplo - en producción esto vendría de una tabla de ventas históricas
                base_sales = total_monthly_revenue * (0.9 + (i * 0.04))  # Crecimiento del 4% mensual
                base_costs = total_monthly_opex * (0.95 + (i * 0.01))   # Inflación del 1% mensual
                
                sales_data.append(round(base_sales, 2))
                cost_data.append(round(base_costs, 2))
            
            return {
                "kpis": {
                    "capex": total_capex,
                    "sales_annual": total_monthly_revenue * 12,
                    "opex_monthly": total_monthly_opex,
                    "incidents": offline_count,
                    "active_alerts": offline_count,
                    "online_devices": online_count,
                    "total_devices": len(devices)
                },
                "financials": {
                    "months": months,
                    "sales": sales_data,
                    "maintenance": cost_data
                }
            }
        except Exception as e:
            logger.error(f"Error obteniendo datos dashboard: {e}")
            return {
                "kpis": {
                    "capex": 0,
                    "sales_annual": 0,
                    "opex_monthly": 0,
                    "incidents": 0,
                    "active_alerts": 0,
                    "online_devices": 0,
                    "total_devices": 0
                },
                "financials": {
                    "months": [],
                    "sales": [],
                    "maintenance": []
                }
            }

# Instancia global del servicio
techview_service = TechViewService()

# RUTAS DEL BLUEPRINT

# RUTA PRINCIPAL DEL DASHBOARD - ESTO ES LO QUE FALTA
@bp.route('/')
def index():
    """Página principal del dashboard de TechView"""
    return render_template('techview_dashboard.html')  # Este es el HTML que me compartiste

@bp.route('/management')
def management():
    """Página de gestión individual de dispositivo"""
    device_id = request.args.get('device_id', '')
    return render_template('techview.html', device_id=unquote(device_id))

@bp.route('/api/device/<path:device_id>')
def api_device(device_id):
    """API para obtener datos de un dispositivo específico"""
    try:
        result = techview_service.get_device_detail(device_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error en API device: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@bp.route('/api/save', methods=['POST'])
def api_save():
    """API para guardar datos financieros"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
        
        success, msg = techview_service.save_device_financials(data)
        return jsonify({
            "success": success, 
            "message": msg, 
            "timestamp": datetime.now().isoformat()
        }), 200 if success else 500
    except Exception as e:
        logger.error(f"Error en API save: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@bp.route('/api/inventory')
def api_inventory():
    """API para obtener inventario de dispositivos"""
    try:
        inventory = techview_service.get_inventory()
        return jsonify(inventory)
    except Exception as e:
        logger.error(f"Error en API inventory: {e}")
        return jsonify([]), 500

@bp.route('/api/dashboard')
def api_dashboard():
    """API para obtener datos del dashboard"""
    try:
        data = techview_service.get_dashboard_data()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error en API dashboard: {e}")
        return jsonify({
            "kpis": {
                "capex": 0,
                "sales_annual": 0,
                "opex_monthly": 0,
                "incidents": 0,
                "active_alerts": 0,
                "online_devices": 0,
                "total_devices": 0
            },
            "financials": {
                "months": [],
                "sales": [],
                "maintenance": []
            }
        }), 500

# Nueva ruta para propuesta
@bp.route('/proposal')
def proposal():
    """Página para nueva instalación/propuesta"""
    return render_template('techview_proposal.html')
