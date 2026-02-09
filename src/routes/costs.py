# src/routes/costs.py
from flask import Blueprint, request, jsonify, render_template, redirect, url_for
import logging
from datetime import datetime, timedelta
import json
import src

logger = logging.getLogger(__name__)

bp = Blueprint('costs', __name__, url_prefix='/costs')

# --- RUTAS DE NAVEGACIÓN (VISTAS) ---
@bp.route('/installations')
def view_installations():
    return render_template('costs/installations.html')

@bp.route('/maintenance')
def view_maintenance():
    return render_template('costs/maintenance.html')

@bp.route('/sales')
def view_sales():
    return render_template('costs/sales.html')

@bp.route('/dashboard')
def view_dashboard():
    return render_template('costs/dashboard.html')

# --- RUTAS TECHVIEW (NUEVO SISTEMA FINANCIERO) ---
@bp.route('/techview')
def view_techview_dashboard():
    """Dashboard principal del sistema financiero"""
    return render_template('dashboard_finanzas.html')

@bp.route('/techview/management')
def view_techview_management():
    """Página de gestión financiera individual"""
    device_id = request.args.get('device_id', '')
    if not device_id:
        return redirect(url_for('costs.view_techview_dashboard'))
    return render_template('techview.html', device_id=device_id)

@bp.route('/techview/pauta')
def view_pauta_management():
    """Página de gestión de pautas"""
    return render_template('pauta_management.html')

# --- API: GUARDAR DATOS BÁSICOS ---
@bp.route('/add', methods=['POST'])
def add_transaction():
    try:
        data = request.get_json()
        if not data.get('device_id') or not data.get('amount'):
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        payload = {
            "device_id": data.get('device_id'),
            "location": data.get('device_id'), # Usamos el ID como ubicación por defecto
            "type": data.get('type'),
            "subtype": data.get('subtype'),
            "description": data.get('description'),
            "amount": float(data.get('amount')),
            "date": data.get('date', datetime.now().strftime('%Y-%m-%d'))
        }

        src.supabase.client.table('finances').insert(payload).execute()
        return jsonify({"status": "success", "message": "Guardado"})
    except Exception as e:
        logger.error(f"Error finance: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API: REPORTE FINANCIERO (Lógica de Negocio) ---
@bp.route('/report', methods=['GET'])
def get_financial_report():
    try:
        response = src.supabase.client.table('finances').select('*').execute()
        transactions = response.data
        
        report = {}

        # 1. Sumarizar datos
        for t in transactions:
            dev = t.get('device_id')
            if dev not in report:
                report[dev] = {
                    "device_id": dev,
                    "cost_installation": 0.0,
                    "cost_maintenance": 0.0,
                    "total_sales": 0.0
                }
            
            amount = float(t['amount'])
            tipo = t['type']
            
            if tipo == 'installation':
                report[dev]['cost_installation'] += amount
            elif tipo == 'maintenance':
                report[dev]['cost_maintenance'] += amount
            elif tipo == 'sale':
                report[dev]['total_sales'] += amount

        # 2. Calcular ROI y Totales
        results = []
        for dev, data in report.items():
            total_expenses = data['cost_installation'] + data['cost_maintenance']
            net_profit = data['total_sales'] - total_expenses
            
            roi = 0
            status = "PÉRDIDA"
            
            if total_expenses > 0:
                roi = (data['total_sales'] / total_expenses) * 100
                if roi >= 100: status = "RENTABLE"
                elif roi > 50: status = "RECUPERANDO"
            elif data['total_sales'] > 0:
                status = "RENTABLE"
                roi = 100

            data['total_expenses'] = total_expenses
            data['net_profit'] = net_profit
            data['roi_percent'] = round(roi, 1)
            data['status_label'] = status
            
            results.append(data)

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- API: TECHVIEW - SISTEMA COMPLETO ---
@bp.route('/api/overview', methods=['GET'])
def get_financial_overview():
    """Obtiene resumen financiero de todas las pantallas"""
    try:
        # Obtener todos los registros financieros
        response = src.supabase.client.table('finances').select('*').execute()
        finances_data = response.data
        
        if not finances_data:
            return jsonify({
                "overview_data": [],
                "totals": {
                    "device_count": 0,
                    "total_capex": 0,
                    "total_monthly_opex": 0,
                    "total_monthly_revenue": 0,
                    "total_margin_monthly": 0,
                    "average_roi": 0
                },
                "revenue_breakdown": {
                    "labels": ["Sin datos"],
                    "values": [0]
                }
            })
        
        overview_data = []
        total_capex = 0
        total_monthly_opex = 0
        total_monthly_revenue = 0
        total_margin_monthly = 0
        total_roi = 0
        roi_count = 0
        
        for finance in finances_data:
            # Calcular totales
            capex = finance.get('total_capex') or 0
            opex_monthly = finance.get('total_opex_monthly') or 0
            revenue_monthly = finance.get('revenue_monthly') or 0
            margin_monthly = revenue_monthly - opex_monthly
            
            # Calcular ROI en meses
            roi_months = 0
            if margin_monthly > 0 and capex > 0:
                roi_months = capex / margin_monthly
            
            device_data = {
                "device_id": finance.get('device_id', ''),
                "location": finance.get('location', ''),
                "total_capex": float(capex),
                "total_opex_monthly": float(opex_monthly),
                "revenue_monthly": float(revenue_monthly),
                "monthly_margin": float(margin_monthly),
                "roi_months": round(roi_months, 1),
                "status": "active"
            }
            
            overview_data.append(device_data)
            
            # Sumar totales globales
            total_capex += float(capex)
            total_monthly_opex += float(opex_monthly)
            total_monthly_revenue += float(revenue_monthly)
            total_margin_monthly += float(margin_monthly)
            if roi_months > 0:
                total_roi += roi_months
                roi_count += 1
        
        # Calcular ROI promedio
        average_roi = total_roi / roi_count if roi_count > 0 else 0
        
        # Datos para gráfico de distribución de ingresos
        revenue_breakdown = {
            "labels": ["CAPEX Recuperado", "OPEX Cubierto", "Margen"],
            "values": [
                total_capex if total_capex < total_margin_monthly else total_margin_monthly,
                total_monthly_opex,
                max(0, total_margin_monthly - total_monthly_opex)
            ]
        }
        
        return jsonify({
            "overview_data": overview_data,
            "totals": {
                "device_count": len(finances_data),
                "total_capex": total_capex,
                "total_monthly_opex": total_monthly_opex,
                "total_monthly_revenue": total_monthly_revenue,
                "total_margin_monthly": total_margin_monthly,
                "average_roi": round(average_roi, 1)
            },
            "revenue_breakdown": revenue_breakdown
        })
        
    except Exception as e:
        logger.error(f"Error en overview: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/api/device/<device_id>', methods=['GET'])
def get_device_financials(device_id):
    """Obtiene datos financieros detallados de una pantalla específica"""
    try:
        # Obtener datos financieros de la pantalla
        response = src.supabase.client.table('finances').select('*').eq('device_id', device_id).execute()
        
        if not response.data:
            return jsonify({"error": "Device not found"}), 404
        
        finance_data = response.data[0]
        
        # Calcular métricas
        capex = finance_data.get('total_capex') or 0
        opex_monthly = finance_data.get('total_opex_monthly') or 0
        revenue_monthly = finance_data.get('revenue_monthly') or 0
        margin_monthly = revenue_monthly - opex_monthly
        roi_months = capex / margin_monthly if margin_monthly > 0 else 0
        
        # Calcular KPIs avanzados (simulados por ahora)
        months_operation = 6  # Esto debería calcularse desde la fecha de instalación
        maintenance_total = (finance_data.get('maint_preventivo_horas') or 0) * 423.07 + \
                           (finance_data.get('maint_correctivo_horas') or 0) * 423.07
        
        # Calcular porcentaje de disponibilidad (simulado)
        availability_rate = 98.7
        
        # Calcular tasa de reincidencia basada en mantenimientos
        prev_horas = finance_data.get('maint_preventivo_horas') or 0
        corr_horas = finance_data.get('maint_correctivo_horas') or 0
        total_horas = prev_horas + corr_horas
        reincidence_rate = (corr_horas / total_horas * 100) if total_horas > 0 else 0
        
        # Calcular score técnico basado en múltiples factores
        technical_score = 85  # Base
        if margin_monthly > 0:
            technical_score += 5
        if revenue_monthly > opex_monthly * 1.5:
            technical_score += 5
        if roi_months < 24:
            technical_score += 5
        technical_score = min(100, technical_score)
        
        advanced_kpis = {
            "technical_score": technical_score,
            "reincidence_rate": round(reincidence_rate, 1),
            "months_operation": months_operation,
            "real_maintenance_total": maintenance_total,
            "availability_rate": availability_rate
        }
        
        return jsonify({
            "financials": finance_data,
            "totals": {
                "capex": float(capex),
                "opex_monthly": float(opex_monthly),
                "revenue_monthly": float(revenue_monthly),
                "margin_monthly": float(margin_monthly),
                "roi_months": round(roi_months, 1),
                "profitability": round((margin_monthly / revenue_monthly * 100) if revenue_monthly > 0 else 0, 1)
            },
            "advanced_kpis": advanced_kpis
        })
        
    except Exception as e:
        logger.error(f"Error getting device financials: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/api/devices', methods=['GET'])
def get_all_devices():
    """Obtiene lista de todas las pantallas disponibles"""
    try:
        response = src.supabase.client.table('finances')\
            .select('device_id, location')\
            .order('device_id')\
            .execute()
        
        devices = [{"device_id": d["device_id"], "location": d.get("location", "")} 
                  for d in response.data]
        
        return jsonify(devices)
        
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/api/save', methods=['POST'])
def save_financial_data():
    """Guarda datos financieros de una pantalla"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        
        if not device_id:
            return jsonify({"status": "error", "message": "device_id requerido"}), 400
        
        # Preparar datos para actualizar
        update_data = {}
        campos_financieros = [
            'cost_pantalla', 'cost_obra_civil', 'cost_estructura', 'cost_medidor_cfe',
            'cost_inst_electrica', 'cost_novastar', 'cost_ups', 'cost_nuc',
            'cost_pastilla_100a', 'cost_pastilla_20a', 'cost_camara', 'cost_teltonika',
            'cost_poe', 'cost_cable_hdmi', 'cost_ont_fibra', 'renta_predio',
            'costo_cfe', 'internet_fibra', 'internet_redundancia', 'licencia_teltonika',
            'licencia_teamviewer', 'licencia_cms', 'licencia_hikvision',
            'licencia_ups_portal', 'licencia_qtm', 'maint_preventivo_horas',
            'maint_correctivo_horas', 'cantidad_titanio', 'revenue_monthly',
            'location'  # También actualizar location si viene
        ]
        
        for campo in campos_financieros:
            if campo in data:
                try:
                    update_data[campo] = float(data[campo]) if data[campo] != '' else None
                except:
                    update_data[campo] = None
        
        # Verificar si el registro existe
        response = src.supabase.client.table('finances')\
            .select('device_id')\
            .eq('device_id', device_id)\
            .execute()
        
        if response.data:
            # Actualizar registro existente
            src.supabase.client.table('finances')\
                .update(update_data)\
                .eq('device_id', device_id)\
                .execute()
        else:
            # Crear nuevo registro
            update_data['device_id'] = device_id
            update_data['cost_type'] = data.get('cost_type', 'techview')
            update_data['category'] = data.get('category', 'comprehensive')
            update_data['location'] = data.get('location', '')
            
            src.supabase.client.table('finances')\
                .insert(update_data)\
                .execute()
        
        return jsonify({
            "status": "success", 
            "message": "Datos financieros guardados correctamente"
        })
        
    except Exception as e:
        logger.error(f"Error saving financial data: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/device/<device_id>/revenue', methods=['PUT'])
def update_device_revenue(device_id):
    """Actualiza el revenue mensual de una pantalla"""
    try:
        data = request.get_json()
        revenue_monthly = data.get('revenue_monthly')
        
        if revenue_monthly is None:
            return jsonify({"status": "error", "message": "revenue_monthly requerido"}), 400
        
        # Actualizar el revenue
        src.supabase.client.table('finances')\
            .update({'revenue_monthly': float(revenue_monthly)})\
            .eq('device_id', device_id)\
            .execute()
        
        return jsonify({
            "status": "success", 
            "message": "Revenue actualizado correctamente"
        })
        
    except Exception as e:
        logger.error(f"Error updating revenue: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API: GESTIÓN DE PAUTAS ---
@bp.route('/api/pautas/active', methods=['GET'])
def get_active_pautas():
    """Obtiene todas las pautas activas"""
    try:
        # Primero verificar si la tabla existe
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            response = src.supabase.client.table('pautas_publicitarias')\
                .select('*')\
                .eq('status', 'active')\
                .gte('fecha_fin', today)\
                .order('fecha_inicio', desc=True)\
                .execute()
        except Exception as table_error:
            logger.warning(f"Tabla pautas no existe aún: {table_error}")
            return jsonify([])
        
        pautas = []
        for pauta in response.data:
            pautas.append({
                "id": pauta.get('id'),
                "device_id": pauta.get('device_id'),
                "cliente": pauta.get('cliente'),
                "monto": float(pauta.get('monto', 0)),
                "fecha_inicio": pauta.get('fecha_inicio'),
                "fecha_fin": pauta.get('fecha_fin'),
                "notas": pauta.get('notas'),
                "status": pauta.get('status')
            })
        
        return jsonify(pautas)
        
    except Exception as e:
        logger.error(f"Error getting active pautas: {e}")
        return jsonify([])

@bp.route('/api/device/<device_id>/pautas', methods=['GET'])
def get_device_pautas(device_id):
    """Obtiene las pautas de una pantalla específica"""
    try:
        try:
            response = src.supabase.client.table('pautas_publicitarias')\
                .select('*')\
                .eq('device_id', device_id)\
                .order('fecha_inicio', desc=True)\
                .execute()
        except Exception as table_error:
            logger.warning(f"Tabla pautas no existe: {table_error}")
            return jsonify([])
        
        pautas = []
        for pauta in response.data:
            pautas.append({
                "id": pauta.get('id'),
                "device_id": pauta.get('device_id'),
                "cliente": pauta.get('cliente'),
                "monto": float(pauta.get('monto', 0)),
                "fecha_inicio": pauta.get('fecha_inicio'),
                "fecha_fin": pauta.get('fecha_fin'),
                "notas": pauta.get('notas'),
                "status": pauta.get('status'),
                "created_at": pauta.get('created_at')
            })
        
        return jsonify(pautas)
        
    except Exception as e:
        logger.error(f"Error getting device pautas: {e}")
        return jsonify([])

@bp.route('/api/pauta', methods=['POST'])
def create_pauta():
    """Crea una nueva pauta publicitaria"""
    try:
        data = request.get_json()
        
        required_fields = ['device_id', 'cliente', 'monto', 'fecha_inicio', 'fecha_fin']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"status": "error", "message": f"{field} requerido"}), 400
        
        pauta_data = {
            "device_id": data['device_id'],
            "cliente": data['cliente'],
            "monto": float(data['monto']),
            "fecha_inicio": data['fecha_inicio'],
            "fecha_fin": data['fecha_fin'],
            "notas": data.get('notas'),
            "status": data.get('status', 'active')
        }
        
        # Crear la pauta
        response = src.supabase.client.table('pautas_publicitarias')\
            .insert(pauta_data)\
            .execute()
        
        if response.data:
            # Actualizar automáticamente el revenue de la pantalla
            update_device_revenue_from_pautas(data['device_id'])
            
            return jsonify({
                "status": "success", 
                "message": "Pauta creada correctamente",
                "pauta_id": response.data[0]['id']
            })
        else:
            return jsonify({"status": "error", "message": "Error al crear pauta"}), 500
            
    except Exception as e:
        logger.error(f"Error creating pauta: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/pauta/<int:pauta_id>', methods=['PUT', 'DELETE'])
def manage_pauta(pauta_id):
    """Actualiza o elimina una pauta"""
    try:
        if request.method == 'PUT':
            data = request.get_json()
            
            update_data = {}
            if 'cliente' in data:
                update_data['cliente'] = data['cliente']
            if 'monto' in data:
                update_data['monto'] = float(data['monto'])
            if 'fecha_inicio' in data:
                update_data['fecha_inicio'] = data['fecha_inicio']
            if 'fecha_fin' in data:
                update_data['fecha_fin'] = data['fecha_fin']
            if 'notas' in data:
                update_data['notas'] = data['notas']
            if 'status' in data:
                update_data['status'] = data['status']
            
            update_data['updated_at'] = datetime.now().isoformat()
            
            response = src.supabase.client.table('pautas_publicitarias')\
                .update(update_data)\
                .eq('id', pauta_id)\
                .execute()
            
            if response.data:
                # Obtener device_id para actualizar revenue
                pauta_response = src.supabase.client.table('pautas_publicitarias')\
                    .select('device_id')\
                    .eq('id', pauta_id)\
                    .execute()
                
                if pauta_response.data:
                    device_id = pauta_response.data[0]['device_id']
                    update_device_revenue_from_pautas(device_id)
                
                return jsonify({
                    "status": "success", 
                    "message": "Pauta actualizada correctamente"
                })
            else:
                return jsonify({"status": "error", "message": "Pauta no encontrada"}), 404
        
        elif request.method == 'DELETE':
            # Obtener device_id antes de eliminar
            pauta_response = src.supabase.client.table('pautas_publicitarias')\
                .select('device_id')\
                .eq('id', pauta_id)\
                .execute()
            
            device_id = None
            if pauta_response.data:
                device_id = pauta_response.data[0]['device_id']
            
            # Eliminar la pauta
            response = src.supabase.client.table('pautas_publicitarias')\
                .delete()\
                .eq('id', pauta_id)\
                .execute()
            
            # Actualizar revenue si había un device_id
            if device_id:
                update_device_revenue_from_pautas(device_id)
            
            return jsonify({
                "status": "success", 
                "message": "Pauta eliminada correctamente"
            })
            
    except Exception as e:
        logger.error(f"Error managing pauta: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- FUNCIONES AUXILIARES ---
def update_device_revenue_from_pautas(device_id):
    """Función auxiliar para actualizar revenue basado en pautas activas"""
    try:
        # Calcular revenue total de pautas activas
        today = datetime.now().strftime('%Y-%m-%d')
        
        response = src.supabase.client.table('pautas_publicitarias')\
            .select('monto')\
            .eq('device_id', device_id)\
            .eq('status', 'active')\
            .gte('fecha_fin', today)\
            .execute()
        
        total_revenue = sum(float(p['monto']) for p in response.data) if response.data else 0
        
        # Actualizar en la tabla finances
        src.supabase.client.table('finances')\
            .update({'revenue_monthly': total_revenue})\
            .eq('device_id', device_id)\
            .execute()
            
    except Exception as e:
        logger.error(f"Error updating revenue from pautas: {e}")

# --- RUTAS DE PRUEBA Y DEBUG ---
@bp.route('/api/test', methods=['GET'])
def test_api():
    """Endpoint de prueba para verificar que la API funciona"""
    try:
        # Verificar conexión a Supabase
        response = src.supabase.client.table('finances').select('count', count='exact').execute()
        
        return jsonify({
            "status": "success",
            "message": "API funcionando correctamente",
            "database_connection": "OK",
            "total_records": response.count if hasattr(response, 'count') else 'N/A'
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "database_connection": "FAILED"
        }), 500

@bp.route('/api/init-tables', methods=['POST'])
def init_tables():
    """Inicializa las tablas necesarias (solo para desarrollo)"""
    try:
        # SQL para crear tabla de pautas si no existe
        sql = """
        CREATE TABLE IF NOT EXISTS pautas_publicitarias (
            id SERIAL PRIMARY KEY,
            device_id TEXT NOT NULL REFERENCES finances(device_id),
            cliente TEXT NOT NULL,
            monto DECIMAL(10,2) NOT NULL DEFAULT 0,
            fecha_inicio DATE NOT NULL,
            fecha_fin DATE NOT NULL,
            notas TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_pautas_device_id ON pautas_publicitarias(device_id);
        CREATE INDEX IF NOT EXISTS idx_pautas_status ON pautas_publicitarias(status);
        CREATE INDEX IF NOT EXISTS idx_pautas_fecha_fin ON pautas_publicitarias(fecha_fin);
        """
        
        # Ejecutar SQL (esto depende de cómo funcione tu cliente Supabase)
        # Nota: Puede que necesites ejecutar esto manualmente en la consola de Supabase
        
        return jsonify({
            "status": "success",
            "message": "Script de inicialización listo. Ejecuta manualmente en Supabase:",
            "sql": sql
        })
        
    except Exception as e:
        logger.error(f"Error initializing tables: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ERROR HANDLERS ---
@bp.errorhandler(404)
def not_found_error(error):
    return jsonify({"status": "error", "message": "Endpoint no encontrado"}), 404

@bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Error interno: {error}")
    return jsonify({"status": "error", "message": "Error interno del servidor"}), 500
