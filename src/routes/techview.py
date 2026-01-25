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
    
    # --- NUEVO: PROCESAR LOGS DE MANTENIMIENTO AUTOMÁTICAMENTE ---
    def _process_maintenance_log(self, log_data):
        """
        Procesa un log de mantenimiento y actualiza automáticamente
        los contadores y costos en la tabla finances
        """
        try:
            if not self.client:
                return
            
            device_id = log_data.get('device_id') or log_data.get('pc_name')
            if not device_id:
                return
            
            clean_id = clean_device_id(device_id)
            logger.info(f"🔄 Procesando log de mantenimiento para: {clean_id}")
            
            # Obtener datos financieros actuales
            finance_resp = self.client.table("finances").select("*").eq("device_id", clean_id).execute()
            current_finance = finance_resp.data[0] if finance_resp.data else {}
            
            # Preparar actualizaciones
            updates = {"device_id": clean_id, "updated_at": datetime.now().isoformat()}
            
            # Determinar tipo de mantenimiento
            action = log_data.get('action', '').lower()
            what = log_data.get('what', '').lower()
            
            # 1. ACTUALIZAR CONTADORES BASADOS EN EL TIPO DE ACCIÓN
            if 'preventivo' in action:
                # Incrementar contador de mantenimientos preventivos
                current_count = current_finance.get('maint_visit_count', 0)
                updates['maint_visit_count'] = self._safe_int(current_count) + 1
                
                # Actualizar costo preventivo bimestral si existe en el log
                cost = log_data.get('cost') or log_data.get('total_cost')
                if cost and self._safe_float(cost) > 0:
                    updates['maint_prev_bimonthly'] = self._safe_float(current_finance.get('maint_prev_bimonthly', 0)) + self._safe_float(cost)
                
                logger.info(f"✅ Mantenimiento preventivo registrado. Visitas: {updates['maint_visit_count']}")
                
            elif 'correctivo' in action:
                # Incrementar contador de mantenimientos correctivos
                current_count = current_finance.get('maint_corr_visit_count', 0)
                updates['maint_corr_visit_count'] = self._safe_int(current_count) + 1
                
                # Actualizar costos correctivos según componentes
                cost = log_data.get('cost') or log_data.get('total_cost')
                if cost and self._safe_float(cost) > 0:
                    # Distribuir costo según descripción
                    desc = log_data.get('desc', '').lower()
                    
                    if any(word in desc for word in ['mano', 'labor', 'tecnico', 'servicio']):
                        updates['maint_corr_labor'] = self._safe_float(current_finance.get('maint_corr_labor', 0)) + self._safe_float(cost)
                    elif any(word in desc for word in ['parte', 'componente', 'repuesto', 'pieza', 'hardware']):
                        updates['maint_corr_parts'] = self._safe_float(current_finance.get('maint_corr_parts', 0)) + self._safe_float(cost)
                    elif any(word in desc for word in ['gasolina', 'combustible', 'transporte', 'viaje']):
                        updates['maint_corr_gas'] = self._safe_float(current_finance.get('maint_corr_gas', 0)) + self._safe_float(cost)
                    else:
                        # Por defecto, asignar a labor
                        updates['maint_corr_labor'] = self._safe_float(current_finance.get('maint_corr_labor', 0)) + self._safe_float(cost)
                
                logger.info(f"🔧 Mantenimiento correctivo registrado. Visitas: {updates['maint_corr_visit_count']}")
                
            elif 'cambio' in action or 'hardware' in action.lower() or any(word in what for word in ['ssd', 'ram', 'cpu', 'pantalla', 'tarjeta']):
                # Incrementar contador de cambios
                current_count = current_finance.get('maint_corr_visit_count', 0)
                updates['maint_corr_visit_count'] = self._safe_int(current_count) + 1
                
                # Actualizar costo de partes
                cost = log_data.get('cost') or log_data.get('total_cost')
                if cost and self._safe_float(cost) > 0:
                    updates['maint_corr_parts'] = self._safe_float(current_finance.get('maint_corr_parts', 0)) + self._safe_float(cost)
                
                logger.info(f"🔄 Cambio de hardware registrado. Costo partes: ${self._safe_float(cost)}")
            
            # 2. ACTUALIZAR COSTOS GENERALES DE MANTENIMIENTO
            cost = log_data.get('cost') or log_data.get('total_cost')
            if cost and self._safe_float(cost) > 0:
                # Sumar al costo total de mantenimiento (campo calculado)
                total_maint_cost = self._safe_float(current_finance.get('total_maintenance_cost', 0))
                updates['total_maintenance_cost'] = total_maint_cost + self._safe_float(cost)
                
                # También sumar a mantenimiento general si no hay categoría específica
                if 'maint_corr_labor' not in updates and 'maint_corr_parts' not in updates and 'maint_corr_gas' not in updates:
                    updates['maint_corr_labor'] = self._safe_float(current_finance.get('maint_corr_labor', 0)) + self._safe_float(cost)
            
            # 3. ACTUALIZAR TAMAÑO DE CREW SI SE ESPECIFICA
            crew_info = log_data.get('executed_by', '')
            if crew_info and ('tecnico' in crew_info.lower() or 'equipo' in crew_info.lower()):
                # Extraer número de técnicos del texto
                import re
                numbers = re.findall(r'\d+', crew_info)
                if numbers:
                    crew_size = int(numbers[0])
                    if 1 <= crew_size <= 10:  # Validación razonable
                        updates['maint_crew_size'] = crew_size
            
            # 4. ACTUALIZAR ÚLTIMA FECHA DE MANTENIMIENTO
            log_date = log_data.get('timestamp') or log_data.get('log_date') or datetime.now().isoformat()
            updates['last_maintenance_date'] = log_date
            
            # 5. GUARDAR ACTUALIZACIONES EN FINANCES
            if len(updates) > 2:  # Más que solo device_id y updated_at
                logger.info(f"💾 Actualizando finanzas con: {updates}")
                self.client.table("finances").upsert(updates, on_conflict="device_id").execute()
                
                # Actualizar también la última fecha en devices
                self.client.table("devices").upsert({
                    "device_id": clean_id,
                    "last_maintenance": log_date,
                    "updated_at": datetime.now().isoformat()
                }, on_conflict="device_id").execute()
                
                logger.info(f"✅ Datos financieros actualizados automáticamente para {clean_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error procesando log de mantenimiento: {e}")
            return False
    
    # --- MÉTODO MODIFICADO: Guardar log con procesamiento automático ---
    def save_maintenance_log(self, log_data):
        """
        Guarda un log de mantenimiento y automáticamente actualiza las finanzas
        """
        try:
            if not self.client:
                return False, "Sin conexión a base de datos"
            
            # 1. Guardar el log en maintenance_logs
            log_to_save = {
                "device_id": log_data.get('device_id') or log_data.get('pc_name'),
                "pc_name": log_data.get('pc_name'),
                "action": log_data.get('action', 'Preventivo'),
                "what": log_data.get('what', 'General'),
                "description": log_data.get('desc') or log_data.get('description', 'Sin descripción'),
                "requested_by": log_data.get('req') or log_data.get('requested_by', 'S/N'),
                "executed_by": log_data.get('exec') or log_data.get('executed_by', 'S/N'),
                "cost": log_data.get('cost') or log_data.get('total_cost', 0),
                "is_solved": log_data.get('is_solved', True),
                "timestamp": datetime.now().isoformat()
            }
            
            # Limpiar campos
            clean_id = clean_device_id(log_to_save['device_id'])
            log_to_save['device_id'] = clean_id
            
            logger.info(f"📝 Guardando log para: {clean_id}")
            
            # Guardar en la tabla de logs
            result = self.client.table("maintenance_logs").insert(log_to_save).execute()
            
            # 2. PROCESAR EL LOG PARA ACTUALIZAR FINANZAS AUTOMÁTICAMENTE
            self._process_maintenance_log(log_to_save)
            
            return True, "Log guardado y finanzas actualizadas automáticamente"
            
        except Exception as e:
            logger.error(f"❌ Error guardando log: {e}")
            return False, f"Error: {str(e)}"
    
    # --- LÓGICA DE DASHBOARD EJECUTIVO ---
    def get_dashboard_data(self):
        """Obtiene datos consolidados para el dashboard ejecutivo"""
        try:
            if not self.client: 
                return {"overview_data": [], "totals": {}}
            
            # Obtener datos brutos
            devices = self.client.table("devices").select("*").execute().data or []
            finances = self.client.table("finances").select("*").execute().data or []
            
            total_capex = 0
            total_revenue = 0
            total_opex = 0
            total_maintenance = 0
            online_count = 0
            alert_count = 0
            
            overview_data = [] # Lista detallada para la tabla
            
            # Indexar finanzas para búsqueda rápida
            fin_map = {f['device_id']: f for f in finances}
            
            for dev in devices:
                dev_id = dev.get('device_id')
                fin = fin_map.get(dev_id, {})
                
                # Calcular CAPEX (Suma de todo lo que empieza con capex_)
                d_capex = sum(self._safe_float(v) for k,v in fin.items() if k.startswith('capex_'))
                
                # Ingresos
                d_rev = self._safe_float(fin.get('revenue_monthly', 0))
                
                # OPEX Simple (Suma de opex_ y maint_)
                d_opex = 0
                for k,v in fin.items():
                    if k.startswith('opex_') and 'annual' not in k: 
                        d_opex += self._safe_float(v)
                    if k.startswith('maint_') and 'count' not in k and 'date' not in k: 
                        d_opex += self._safe_float(v)
                    if k == 'total_maintenance_cost':
                        total_maintenance += self._safe_float(v)
                
                # Licencia Anual Prorrateada
                if 'opex_license_annual' in fin:
                    d_opex += (self._safe_float(fin['opex_license_annual']) / 12)

                d_margin = d_rev - d_opex
                d_roi = (d_capex / d_margin) if d_margin > 0 else 0
                
                # Totales Globales
                total_capex += d_capex
                total_revenue += d_rev
                total_opex += d_opex
                
                if dev.get('status') == 'online': 
                    online_count += 1
                if d_margin < 0 or dev.get('status') == 'offline': 
                    alert_count += 1
                
                # Obtener contadores de mantenimiento
                maint_preventive = fin.get('maint_visit_count', 0)
                maint_corrective = fin.get('maint_corr_visit_count', 0)
                
                # Datos por fila
                overview_data.append({
                    "device_id": dev_id,
                    "pc_name": dev.get('pc_name') or dev_id,
                    "status": dev.get('status', 'unknown'),
                    "monthly_revenue": d_rev,
                    "monthly_opex": d_opex,
                    "monthly_margin": d_margin,
                    "capex": d_capex,
                    "roi_months": d_roi,
                    "maint_preventive": maint_preventive,
                    "maint_corrective": maint_corrective,
                    "total_maintenance_cost": fin.get('total_maintenance_cost', 0)
                })

            # Gráfica Histórica Simulada (basada en totales actuales)
            months = []
            sales_hist = []
            cost_hist = []
            current_date = datetime.now()
            
            for i in range(5, -1, -1):
                month_label = (current_date - timedelta(days=30*i)).strftime("%b")
                months.append(month_label)
                # Variación leve para simular historia
                sales_hist.append(total_revenue * (1 - (i * 0.02))) 
                cost_hist.append(total_opex * (1 + (i * 0.01)))

            return {
                "totals": {
                    "total_capex": total_capex,
                    "total_monthly_revenue": total_revenue,
                    "total_monthly_opex": total_opex,
                    "total_maintenance_cost": total_maintenance,
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

    # --- MÉTODOS DE GESTIÓN INDIVIDUAL ---
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
            
            # Agregar estadísticas de mantenimiento
            maint_stats = self._get_maintenance_stats(clean_id, maintenance_logs)
            
            return {
                "device": device_data,
                "financials": finance_data,
                "maintenance_logs": maintenance_logs,
                "maintenance_stats": maint_stats,
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

    def _get_maintenance_stats(self, device_id, logs):
        """Calcula estadísticas de mantenimiento"""
        try:
            if not logs:
                return {
                    "total_logs": 0,
                    "preventive_count": 0,
                    "corrective_count": 0,
                    "total_cost": 0,
                    "avg_cost_per_visit": 0,
                    "last_maintenance": None
                }
            
            preventive = sum(1 for log in logs if 'preventivo' in str(log.get('action', '')).lower())
            corrective = sum(1 for log in logs if 'correctivo' in str(log.get('action', '')).lower())
            
            total_cost = sum(self._safe_float(log.get('cost', 0)) for log in logs)
            avg_cost = total_cost / len(logs) if logs else 0
            
            # Última fecha de mantenimiento
            dates = [log.get('timestamp') or log.get('log_date') for log in logs if log.get('timestamp') or log.get('log_date')]
            last_date = max(dates) if dates else None
            
            return {
                "total_logs": len(logs),
                "preventive_count": preventive,
                "corrective_count": corrective,
                "total_cost": round(total_cost, 2),
                "avg_cost_per_visit": round(avg_cost, 2),
                "last_maintenance": last_date
            }
        except Exception as e:
            logger.error(f"Error calculando stats mantenimiento: {e}")
            return {}

    def _get_device_info(self, device_id):
        try:
            if not self.client: 
                return {"device_id": device_id, "status": "unknown"}
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            if dev_resp.data: 
                return dev_resp.data[0]
            else: 
                return {"device_id": device_id, "status": "active", "location": device_id}
        except: 
            return {"device_id": device_id, "status": "unknown"}

    def _get_finance_info(self, device_id):
        try:
            if not self.client: 
                return {}
            
            # Obtener datos financieros
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            finance_data = fin_resp.data[0] if fin_resp.data else {}
            
            # Si no existe registro, crear uno básico
            if not finance_data:
                finance_data = {
                    "device_id": device_id,
                    "maint_visit_count": 0,
                    "maint_corr_visit_count": 0,
                    "maint_prev_bimonthly": 0,
                    "maint_corr_labor": 0,
                    "maint_corr_parts": 0,
                    "maint_corr_gas": 0,
                    "total_maintenance_cost": 0
                }
            
            return finance_data
        except Exception as e:
            logger.error(f"Error obteniendo info financiera: {e}")
            return {}

    def _get_maintenance_logs(self, device_id):
        try:
            if not self.client: 
                return []
            
            logs = self.client.table("maintenance_logs").select("*").eq("device_id", device_id).order("timestamp", desc=True).limit(50).execute().data
            
            # Asegurar formato consistente
            for log in logs:
                if 'cost' not in log:
                    log['cost'] = 0
                if 'total_cost' not in log:
                    log['total_cost'] = log.get('cost', 0)
            
            return logs
        except Exception as e:
            logger.error(f"Error obteniendo logs: {e}")
            return []

    def _calculate_basic_totals(self, finance_data):
        capex = opex = revenue = maintenance = 0
        
        if finance_data:
            for k, v in finance_data.items():
                if k.startswith('capex_'): 
                    capex += self._safe_float(v)
                
                if k.startswith('opex_') and 'annual' not in k: 
                    opex += self._safe_float(v)
                
                if k == 'revenue_monthly': 
                    revenue = self._safe_float(v)
                
                # Sumar costos de mantenimiento
                if k.startswith('maint_') and 'count' not in k and 'date' not in k: 
                    val = self._safe_float(v)
                    if 'bimonthly' in k: 
                        opex += val/2  # Bimestral -> mensual
                    else: 
                        opex += val
                
                if k == 'total_maintenance_cost':
                    maintenance = self._safe_float(v)
        
        margin = revenue - opex
        roi_months = (capex / margin) if margin > 0 else 0
        
        return {
            "capex": round(capex, 2),
            "opex_monthly": round(opex, 2),
            "revenue_monthly": round(revenue, 2),
            "margin_monthly": round(margin, 2),
            "roi_months": round(roi_months, 2),
            "total_maintenance_cost": round(maintenance, 2)
        }

    def _calculate_advanced_kpis(self, finance_data, logs, device):
        try:
            # Calcular score técnico basado en mantenimiento
            maint_score = 100
            if logs:
                corrective = sum(1 for log in logs if 'correctivo' in str(log.get('action', '')).lower())
                total_logs = len(logs)
                corrective_ratio = corrective / total_logs if total_logs > 0 else 0
                
                if corrective_ratio > 0.7:
                    maint_score -= 40
                elif corrective_ratio > 0.4:
                    maint_score -= 20
                
                # Penalizar por alto costo de mantenimiento
                total_maint_cost = finance_data.get('total_maintenance_cost', 0)
                capex = sum(self._safe_float(v) for k,v in finance_data.items() if k.startswith('capex_'))
                if capex > 0:
                    maint_cost_ratio = total_maint_cost / capex
                    if maint_cost_ratio > 0.5:
                        maint_score -= 30
                    elif maint_cost_ratio > 0.2:
                        maint_score -= 15
            
            return {
                "technical_score": max(0, min(100, maint_score)),
                "reincidence_rate": round((finance_data.get('maint_corr_visit_count', 0) / max(1, finance_data.get('maint_visit_count', 1))) * 100, 1),
                "health_status": {
                    "status": "Excelente" if maint_score >= 85 else "Bueno" if maint_score >= 70 else "Regular" if maint_score >= 50 else "Crítico",
                    "color": "emerald" if maint_score >= 85 else "green" if maint_score >= 70 else "yellow" if maint_score >= 50 else "red"
                },
                "total_current_cost": round(sum(self._safe_float(v) for k,v in finance_data.items() if k.startswith('capex_')) + finance_data.get('total_maintenance_cost', 0), 2),
                "accumulated_opex": round(finance_data.get('total_maintenance_cost', 0) * 6, 2)  # Estimado 6 meses
            }
        except Exception as e:
            logger.error(f"Error calculando KPIs: {e}")
            return {
                "technical_score": 85,
                "reincidence_rate": 0,
                "health_status": {"status": "OK", "color": "green"},
                "total_current_cost": 0,
                "accumulated_opex": 0
            }

    def _calculate_eco_impact(self, totals):
        return {"kwh_saved": 0, "co2_tons": 0}

    def _get_financial_projections(self, device_id):
        return []

    def _generate_summary(self, totals, kpis, device):
        return {
            "financial_health": "OK",
            "overall_rating": 4,
            "maintenance_health": kpis.get('health_status', {}).get('status', 'Desconocido')
        }

    def _create_error_response(self, device_id, msg):
        return {"error": msg}

    def save_device_financials(self, payload):
        try:
            if not self.client: 
                return False, "Sin conexión DB"
            
            device_id = payload.get('device_id')
            if not device_id: 
                return False, "Falta Device ID"
            
            clean_id = clean_device_id(device_id)
            
            data = {"device_id": clean_id, "updated_at": datetime.now().isoformat()}
            
            # Copiar solo los campos financieros del payload
            finance_fields = [
                'capex_', 'opex_', 'revenue_', 'maint_', 'life_'
            ]
            
            for key, value in payload.items():
                if any(field in key for field in finance_fields):
                    # Convertir tipos de datos apropiadamente
                    if key in ['maint_crew_size', 'maint_visit_count', 'maint_corr_visit_count']:
                        data[key] = self._safe_int(value)
                    elif 'date' in key:
                        data[key] = value  # Mantener como string
                    else:
                        data[key] = self._safe_float(value)
                elif key == 'device_id' or key == 'updated_at':
                    continue  # Ya los tenemos
            
            logger.info(f"💾 Guardando datos financieros: {list(data.keys())}")
            self.client.table("finances").upsert(data, on_conflict="device_id").execute()
            
            # Actualizar devices también
            self.client.table("devices").upsert({
                "device_id": clean_id,
                "updated_at": datetime.now().isoformat()
            }, on_conflict="device_id").execute()
            
            return True, "Datos financieros guardados"
            
        except Exception as e:
            logger.error(f"❌ Error save financials: {e}")
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

# RUTA CRÍTICA PARA EL ERROR 404
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
    """Guardar datos financieros"""
    data = request.get_json()
    success, msg = techview_service.save_device_financials(data)
    return jsonify({"success": success, "message": msg}), 200 if success else 500

# --- NUEVA RUTA: Guardar log de mantenimiento ---
@bp.route('/api/maintenance/save', methods=['POST'])
def api_save_maintenance():
    """Guardar log de mantenimiento y actualizar finanzas automáticamente"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
        
        success, msg = techview_service.save_maintenance_log(data)
        return jsonify({"success": success, "message": msg}), 200 if success else 500
        
    except Exception as e:
        logger.error(f"Error en API save maintenance: {e}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

# --- NUEVA RUTA: Obtener logs de mantenimiento ---
@bp.route('/api/maintenance/logs/<path:device_id>')
def api_get_maintenance_logs(device_id):
    """Obtener logs de mantenimiento para un dispositivo"""
    try:
        logs = techview_service._get_maintenance_logs(device_id)
        return jsonify({"logs": logs}), 200
    except Exception as e:
        logger.error(f"Error obteniendo logs: {e}")
        return jsonify({"logs": [], "error": str(e)}), 500

# --- NUEVA RUTA: Procesar logs existentes ---
@bp.route('/api/maintenance/process-existing')
def api_process_existing_logs():
    """
    Endpoint para procesar todos los logs existentes y actualizar finanzas.
    Útil para migrar datos antiguos.
    """
    try:
        if not techview_service.client:
            return jsonify({"success": False, "message": "No DB connection"}), 500
        
        # Obtener todos los logs
        logs_resp = techview_service.client.table("maintenance_logs").select("*").execute()
        logs = logs_resp.data if logs_resp.data else []
        
        processed = 0
        errors = 0
        
        for log in logs:
            try:
                techview_service._process_maintenance_log(log)
                processed += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error procesando log {log.get('id')}: {e}")
        
        return jsonify({
            "success": True,
            "message": f"Procesados {processed} logs, {errors} errores",
            "processed": processed,
            "errors": errors
        }), 200
        
    except Exception as e:
        logger.error(f"Error procesando logs existentes: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
