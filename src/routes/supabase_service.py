import os
import logging
import traceback
import re
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from supabase import create_client, Client

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Blueprint
techview_bp = Blueprint('techview', __name__, url_prefix='/techview')

def clean_device_id(device_id):
    """
    Limpia el device_id de caracteres problemáticos.
    """
    if not device_id:
        return ""
    
    # Decodificar URL si es necesario
    from urllib.parse import unquote
    try:
        device_id = unquote(device_id)
    except:
        pass
    
    # Reemplazar tabs por espacios
    device_id = device_id.replace('\t', ' ')
    
    # Remover caracteres de control
    device_id = re.sub(r'[\x00-\x1f\x7f]', '', device_id)
    
    # Normalizar espacios múltiples
    device_id = ' '.join(device_id.split())
    
    return device_id.strip()

class SupabaseService:
    def __init__(self):
        try:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            
            if not url:
                logger.error("❌ SUPRABASE_URL no configurado")
                raise ValueError("SUPABASE_URL no configurado")
            if not key:
                logger.error("❌ SUPRABASE_KEY no configurado")
                raise ValueError("SUPABASE_KEY no configurado")
            
            logger.info(f"🔗 Conectando a Supabase...")
            self.client: Client = create_client(url, key)
            
            # Test de conexión simple
            try:
                self.client.table("finances").select("count", count="exact").limit(1).execute()
                logger.info(f"✅ Conexión a Supabase exitosa")
            except:
                # Intentar con devices si finances no existe
                self.client.table("devices").select("count", count="exact").limit(1).execute()
                logger.info(f"✅ Conexión a Supabase exitosa (solo devices)")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando Supabase: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _safe_float(self, value):
        """Convierte seguro a float"""
        try:
            if value is None or value == '':
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    # MÉTODOS PARA COMPATIBILIDAD CON MONITOR_SERVICE
    def buffer_metric(self, *args, **kwargs):
        """Método dummy para compatibilidad con monitor_service"""
        logger.debug(f"buffer_metric called with args: {args}, kwargs: {kwargs}")
        return True
    
    def upsert_device_status(self, device_id, status, location=None):
        """Actualizar estado del dispositivo"""
        try:
            clean_id = clean_device_id(device_id)
            data = {
                "device_id": clean_id,
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
            if location:
                data["location"] = location
            
            result = self.client.table("devices").upsert(data, on_conflict="device_id").execute()
            logger.debug(f"Device status updated: {clean_id} -> {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating device status: {e}")
            return False
    
    def log_metric(self, metric_type, value, device_id=None, tags=None):
        """Método para logging de métricas"""
        try:
            metric_data = {
                "type": metric_type,
                "value": value,
                "timestamp": datetime.now().isoformat()
            }
            if device_id:
                metric_data["device_id"] = clean_device_id(device_id)
            if tags:
                metric_data["tags"] = tags
            
            logger.info(f"METRIC: {metric_type}={value} device={device_id}")
            return True
        except Exception as e:
            logger.error(f"Error logging metric: {e}")
            return False
    
    def get_device_detail(self, device_id):
        """Obtener detalle del dispositivo"""
        try:
            # Limpiar device_id
            clean_id = clean_device_id(device_id)
            logger.debug(f"🔍 Buscando dispositivo: '{clean_id}'")
            
            # 1. Buscar en devices
            try:
                dev_resp = self.client.table("devices").select("*").eq("device_id", clean_id).execute()
                dev_data = dev_resp.data[0] if dev_resp.data else {
                    "device_id": clean_id,
                    "status": "unknown",
                    "location": clean_id
                }
            except Exception as e:
                logger.warning(f"Error buscando device: {e}")
                dev_data = {"device_id": clean_id, "status": "error"}
            
            # 2. Buscar datos financieros
            finance_row = {}
            try:
                fin_resp = self.client.table("finances").select("*").eq("device_id", clean_id).execute()
                if fin_resp.data:
                    finance_row = fin_resp.data[0]
                    logger.debug(f"Finanzas encontradas: {len(finance_row)} campos")
            except Exception as e:
                logger.warning(f"Error buscando finanzas: {e}")
            
            # 3. Calcular totales
            capex = 0.0
            opex = 0.0
            revenue = 0.0
            
            if finance_row:
                for key, value in finance_row.items():
                    if key.startswith('capex_'):
                        capex += self._safe_float(value)
                    elif key.startswith('opex_') and 'annual' not in key:
                        opex += self._safe_float(value)
                    elif key == 'opex_license_annual':
                        opex += (self._safe_float(value) / 12)
                    elif key == 'revenue_monthly':
                        revenue = self._safe_float(value)
            
            # 4. Calcular ROI
            margin = revenue - opex
            roi = (capex / margin) if margin > 0 and capex > 0 else 0
            
            return {
                "device": dev_data,
                "financials": finance_row,
                "totals": {
                    "capex": round(capex, 2),
                    "opex": round(opex, 2),
                    "revenue": round(revenue, 2),
                    "margin": round(margin, 2),
                    "roi": round(roi, 2)
                },
                "history": {"tickets": []},
                "eco": {
                    "kwh_saved": 3500,
                    "co2_tons": 1.5,
                    "trees": 75,
                    "efficiency_gain": "66%"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error en get_device_detail: {str(e)}")
            return {
                "error": str(e),
                "device": {"device_id": device_id, "status": "error"},
                "financials": {},
                "totals": {"capex": 0, "opex": 0, "revenue": 0, "margin": 0, "roi": 0},
                "history": {"tickets": []},
                "eco": {"kwh_saved": 0, "co2_tons": 0, "trees": 0, "efficiency_gain": "0%"}
            }

    def save_device_financials(self, payload):
        """Guardar datos financieros - VERSIÓN CORREGIDA"""
        try:
            logger.info(f"💾 Guardando datos financieros")
            
            # Validación
            raw_device_id = payload.get('device_id')
            if not raw_device_id:
                return False, "device_id es requerido"
            
            clean_id = clean_device_id(raw_device_id)
            logger.info(f"Device ID: '{clean_id}'")
            
            # Verificar si la tabla finances tiene la columna problemática 'cost_type'
            # Si el payload tiene 'cost_type', lo eliminamos
            if 'cost_type' in payload:
                logger.warning(f"⚠️  Eliminando campo 'cost_type' del payload")
                del payload['cost_type']
            
            # Preparar datos limpios
            cleaned_payload = {"device_id": clean_id}
            
            # Solo incluir campos válidos
            valid_fields = [
                'capex_screen', 'capex_civil', 'capex_structure', 'capex_electrical',
                'capex_meter', 'capex_data_install', 'capex_nuc', 'capex_ups',
                'capex_sending', 'capex_processor', 'capex_modem_wifi', 'capex_modem_sim',
                'capex_teltonika', 'capex_hdmi', 'capex_camera', 'capex_crew',
                'capex_logistics', 'capex_legal', 'capex_first_install', 'capex_admin_qtm',
                'opex_light', 'opex_internet', 'opex_rent', 'opex_soil_use',
                'opex_license_annual', 'opex_content_scheduling', 'opex_srd',
                'maint_prev_bimonthly', 'maint_cleaning_supplies', 'maint_gas',
                'maint_corr_parts', 'maint_corr_labor',
                'life_retirement', 'life_renewal', 'life_special',
                'revenue_monthly'
            ]
            
            for field in valid_fields:
                if field in payload:
                    cleaned_payload[field] = self._safe_float(payload[field])
            
            # Timestamp
            cleaned_payload['updated_at'] = datetime.now().isoformat()
            
            logger.debug(f"Payload a guardar: {list(cleaned_payload.keys())}")
            
            # INTENTAR GUARDAR CON MANEJO DE ERRORES DETALLADO
            try:
                # Primero, asegurar que el device existe
                try:
                    self.client.table("devices").upsert({
                        "device_id": clean_id,
                        "status": "active",
                        "updated_at": datetime.now().isoformat()
                    }, on_conflict="device_id").execute()
                except Exception as e:
                    logger.warning(f"Nota: No se pudo actualizar devices: {e}")
                
                # Ahora guardar en finances
                result = self.client.table("finances").upsert(
                    cleaned_payload, 
                    on_conflict="device_id"
                ).execute()
                
                logger.info(f"✅ Guardado exitoso para {clean_id}")
                return True, "Guardado exitoso"
                
            except Exception as db_error:
                logger.error(f"❌ Error de base de datos: {db_error}")
                
                # Verificar si es error de columna faltante
                error_str = str(db_error)
                if "column" in error_str and "does not exist" in error_str:
                    logger.error("⚠️  Error: Columna faltante en la tabla")
                    return False, f"Error de estructura de BD: {error_str}"
                else:
                    return False, f"Error de BD: {error_str}"
            
        except Exception as e:
            logger.error(f"❌ Error crítico en save_device_financials: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"Error crítico: {str(e)}"

# Instancia global
try:
    supabase = SupabaseService()
    logger.info("✅ SupabaseService inicializado correctamente")
except Exception as e:
    logger.error(f"❌ No se pudo inicializar SupabaseService: {e}")
    supabase = None

# ========== ROUTES CON DIAGNÓSTICO INTEGRADO ==========

@techview_bp.route('/diagnostic')
def diagnostic():
    """Página de diagnóstico"""
    return """
    <html>
    <head><title>Diagnóstico TechView</title></head>
    <body>
        <h1>Diagnóstico TechView</h1>
        <div id="results"></div>
        <script>
            async function runDiagnostic() {
                const results = document.getElementById('results');
                results.innerHTML = '<p>Ejecutando diagnóstico...</p>';
                
                const tests = [
                    {name: 'Test DB', url: '/techview/api/test-db'},
                    {name: 'Ver Tablas', url: '/techview/api/check-tables'},
                    {name: 'Crear Tablas', url: '/techview/api/create-tables', method: 'POST'}
                ];
                
                for (const test of tests) {
                    try {
                        const response = await fetch(test.url, {
                            method: test.method || 'GET'
                        });
                        const data = await response.json();
                        results.innerHTML += `
                            <div style="background: ${response.ok ? '#d4edda' : '#f8d7da'}; padding: 10px; margin: 5px; border-radius: 5px;">
                                <h3>${test.name} - ${response.ok ? '✅' : '❌'}</h3>
                                <pre>${JSON.stringify(data, null, 2)}</pre>
                            </div>
                        `;
                    } catch (e) {
                        results.innerHTML += `
                            <div style="background: #f8d7da; padding: 10px; margin: 5px; border-radius: 5px;">
                                <h3>${test.name} - ❌ ERROR</h3>
                                <pre>${e.toString()}</pre>
                            </div>
                        `;
                    }
                }
            }
            runDiagnostic();
        </script>
    </body>
    </html>
    """

@techview_bp.route('/api/test-db')
def api_test_db():
    """API: Probar conexión a base de datos"""
    try:
        if not supabase:
            return jsonify({"status": "error", "message": "Supabase no inicializado"}), 503
        
        results = {"timestamp": datetime.now().isoformat()}
        
        # Probar conexión básica
        try:
            # Intentar contar en finances
            try:
                fin_resp = supabase.client.table("finances").select("count", count="exact").execute()
                results["finances"] = {"exists": True, "count": fin_resp.count}
            except Exception as e:
                results["finances"] = {"exists": False, "error": str(e)}
            
            # Intentar contar en devices
            try:
                dev_resp = supabase.client.table("devices").select("count", count="exact").execute()
                results["devices"] = {"exists": True, "count": dev_resp.count}
            except Exception as e:
                results["devices"] = {"exists": False, "error": str(e)}
            
            # Probar inserción simple
            test_id = f"TEST_{int(datetime.now().timestamp())}"
            test_data = {
                "device_id": test_id,
                "capex_screen": 1000.50,
                "revenue_monthly": 500.75,
                "updated_at": datetime.now().isoformat()
            }
            
            try:
                supabase.client.table("finances").upsert(test_data).execute()
                results["test_insert"] = {"success": True, "id": test_id}
                
                # Limpiar
                supabase.client.table("finances").delete().eq("device_id", test_id).execute()
            except Exception as e:
                results["test_insert"] = {"success": False, "error": str(e)}
            
        except Exception as e:
            results["connection_error"] = str(e)
        
        return jsonify({
            "status": "success",
            "results": results
        })
        
    except Exception as e:
        logger.error(f"❌ Error en api_test_db: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@techview_bp.route('/api/check-tables')
def api_check_tables():
    """API: Verificar estructura de tablas"""
    try:
        if not supabase:
            return jsonify({"error": "Servicio no disponible"}), 503
        
        results = {}
        
        # Verificar tabla finances
        try:
            # Obtener una fila para ver columnas
            fin_resp = supabase.client.table("finances").select("*").limit(1).execute()
            if fin_resp.data:
                sample = fin_resp.data[0]
                results["finances"] = {
                    "exists": True,
                    "columns": list(sample.keys()),
                    "sample": sample
                }
            else:
                # Intentar obtener información del schema
                results["finances"] = {
                    "exists": True,
                    "empty": True,
                    "message": "Tabla vacía"
                }
        except Exception as e:
            results["finances"] = {
                "exists": False,
                "error": str(e)
            }
        
        # Verificar tabla devices
        try:
            dev_resp = supabase.client.table("devices").select("*").limit(1).execute()
            if dev_resp.data:
                results["devices"] = {
                    "exists": True,
                    "columns": list(dev_resp.data[0].keys())
                }
            else:
                results["devices"] = {
                    "exists": True,
                    "empty": True
                }
        except Exception as e:
            results["devices"] = {
                "exists": False,
                "error": str(e)
            }
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"❌ Error en api_check_tables: {e}")
        return jsonify({"error": str(e)}), 500

@techview_bp.route('/api/create-tables', methods=['POST'])
def api_create_tables():
    """API: Crear tablas necesarias"""
    try:
        if not supabase:
            return jsonify({"error": "Servicio no disponible"}), 503
        
        # SQL simplificado - solo columnas esenciales
        sql_commands = [
            # Tabla devices
            """
            CREATE TABLE IF NOT EXISTS devices (
                id BIGSERIAL PRIMARY KEY,
                device_id TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'offline',
                location TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """,
            
            # Tabla finances - versión simplificada
            """
            CREATE TABLE IF NOT EXISTS finances (
                id BIGSERIAL PRIMARY KEY,
                device_id TEXT UNIQUE,
                
                -- Solo columnas esenciales para empezar
                capex_screen NUMERIC DEFAULT 0,
                capex_civil NUMERIC DEFAULT 0,
                capex_structure NUMERIC DEFAULT 0,
                revenue_monthly NUMERIC DEFAULT 0,
                
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """
        ]
        
        results = []
        for i, sql in enumerate(sql_commands):
            try:
                # En Supabase, puedes usar query() para SQL directo
                result = supabase.client.query(sql).execute()
                results.append(f"Comando {i+1}: ✅ Éxito")
                logger.info(f"SQL {i+1} ejecutado")
            except Exception as e:
                error_msg = str(e)
                results.append(f"Comando {i+1}: ❌ Error - {error_msg[:100]}")
                logger.error(f"Error SQL {i+1}: {error_msg}")
        
        return jsonify({
            "success": True,
            "message": "Tablas creadas/verificadas",
            "results": results
        })
        
    except Exception as e:
        logger.error(f"❌ Error en api_create_tables: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@techview_bp.route('/api/fix-table', methods=['POST'])
def api_fix_table():
    """API: Corregir tabla finances (agregar columnas faltantes)"""
    try:
        if not supabase:
            return jsonify({"error": "Servicio no disponible"}), 503
        
        # Lista de columnas a agregar si no existen
        columns_to_add = [
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_electrical NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_meter NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_data_install NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_nuc NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_ups NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_sending NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_processor NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_modem_wifi NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_modem_sim NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_teltonika NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_hdmi NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_camera NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_crew NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_logistics NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_legal NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_first_install NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_admin_qtm NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_light NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_internet NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_rent NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_soil_use NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_license_annual NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_content_scheduling NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_srd NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS maint_prev_bimonthly NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS maint_cleaning_supplies NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS maint_gas NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS maint_corr_parts NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS maint_corr_labor NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS life_retirement NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS life_renewal NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS life_special NUMERIC DEFAULT 0;"
        ]
        
        results = []
        success_count = 0
        
        for i, sql in enumerate(columns_to_add):
            try:
                supabase.client.query(sql).execute()
                results.append(f"Columna {i+1}: ✅ Agregada")
                success_count += 1
            except Exception as e:
                results.append(f"Columna {i+1}: ❌ Error - {str(e)[:50]}")
        
        return jsonify({
            "success": True,
            "message": f"Se agregaron {success_count} de {len(columns_to_add)} columnas",
            "results": results
        })
        
    except Exception as e:
        logger.error(f"❌ Error en api_fix_table: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== ROUTES PRINCIPALES ==========

@techview_bp.route('/management')
def techview_management():
    """Página de gestión de costos"""
    try:
        device_id = request.args.get('device_id', '')
        if not device_id:
            return "device_id es requerido", 400
        
        from urllib.parse import unquote
        device_id = unquote(device_id)
        
        logger.info(f"📱 Cargando gestión para: {device_id}")
        return render_template('techview_management.html', device_id=device_id)
    except Exception as e:
        logger.error(f"❌ Error en techview_management: {e}")
        return render_template('error.html', error=str(e)), 500

@techview_bp.route('/api/device/<path:device_id>')
def api_device_detail(device_id):
    """API: Obtener detalle del dispositivo"""
    try:
        if not supabase:
            return jsonify({"error": "Servicio no disponible"}), 503
        
        detail = supabase.get_device_detail(device_id)
        return jsonify(detail)
    except Exception as e:
        logger.error(f"❌ Error en api_device_detail: {e}")
        return jsonify({"error": str(e)}), 500

@techview_bp.route('/api/save', methods=['POST'])
def api_save_financials():
    """API: Guardar datos financieros - CON DEBUG DETALLADO"""
    try:
        logger.info("=== INICIO DEBUG api_save_financials ===")
        
        if not supabase:
            logger.error("Supabase no disponible")
            return jsonify({"error": "Servicio no disponible"}), 503
        
        # Debug: Ver qué recibimos
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Obtener datos
        data = None
        if request.content_type == 'application/json':
            data = request.get_json()
        else:
            # Intentar parsear como JSON de todos modos
            try:
                raw_data = request.get_data(as_text=True)
                logger.info(f"Raw data: {raw_data[:500]}...")
                import json
                data = json.loads(raw_data)
            except Exception as e:
                logger.error(f"Error parsing JSON: {e}")
                return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400
        
        if not data:
            logger.error("No data received")
            return jsonify({"error": "No se recibieron datos"}), 400
        
        logger.info(f"Data received: {list(data.keys())}")
        logger.info(f"Device ID in data: {data.get('device_id')}")
        
        # Guardar
        success, message = supabase.save_device_financials(data)
        
        logger.info(f"Save result: success={success}, message={message}")
        logger.info("=== FIN DEBUG api_save_financials ===")
        
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 500
            
    except Exception as e:
        logger.error(f"❌ Error en api_save_financials: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
