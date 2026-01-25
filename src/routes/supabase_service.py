import os
import logging
import traceback
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from supabase import create_client, Client

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Blueprint
techview_bp = Blueprint('techview', __name__, url_prefix='/techview')

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
            
            logger.info(f"🔗 Conectando a Supabase: {url[:30]}...")
            self.client: Client = create_client(url, key)
            
            # Test de conexión
            test = self.client.table("finances").select("count", count="exact").limit(1).execute()
            logger.info(f"✅ Conexión a Supabase exitosa. Tabla 'finances' accesible")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando Supabase: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _safe_float(self, value):
        try:
            return float(value) if value is not None and value != '' else 0.0
        except (ValueError, TypeError) as e:
            logger.debug(f"⚠️  Error convirtiendo a float: {value} -> {e}")
            return 0.0

    def _calculate_eco_impact(self):
        try:
            kwh_saved = ((450 - 150) * 18 * 365) / 1000
            co2_tons = (kwh_saved * 0.45) / 1000
            trees = int(co2_tons * 50)
            return {
                "kwh_saved": round(kwh_saved, 0),
                "co2_tons": round(co2_tons, 2),
                "trees": trees,
                "efficiency_gain": "66%"
            }
        except Exception as e:
            logger.error(f"Error cálculo eco: {e}")
            return {"kwh_saved": 0, "co2_tons": 0, "trees": 0, "efficiency_gain": "0%"}

    def get_financial_overview(self):
        try:
            logger.debug("📊 Obteniendo overview financiero...")
            
            # Obtener finanzas
            finances_resp = self.client.table("finances").select("*").execute()
            finances = finances_resp.data if finances_resp.data else []
            logger.debug(f"📈 Finanzas encontradas: {len(finances)} registros")
            
            # Obtener tickets
            tickets_resp = self.client.table("tickets").select("id").execute()
            tickets = tickets_resp.data if tickets_resp.data else []
            
            # Obtener dispositivos
            devices_resp = self.client.table("devices").select("status").execute()
            devices = devices_resp.data if devices_resp.data else []

            capex_total = 0.0
            opex_total = 0.0
            sales_total = 0.0

            for f in finances:
                # Sumar CAPEX
                capex_keys = [k for k in f.keys() if k.startswith('capex_')]
                for k in capex_keys:
                    val = self._safe_float(f.get(k))
                    capex_total += val
                
                # Sumar OPEX (mensual)
                opex_keys = [k for k in f.keys() if k.startswith('opex_') and 'annual' not in k]
                for k in opex_keys:
                    val = self._safe_float(f.get(k))
                    opex_total += val
                
                # Licencia anual convertida a mensual
                license_annual = self._safe_float(f.get('opex_license_annual', 0))
                opex_total += (license_annual / 12)
                
                # Ventas
                sales_total += self._safe_float(f.get('revenue_monthly', 0))

            result = {
                "kpis": {
                    "capex": round(capex_total, 2),
                    "sales_annual": round(sales_total * 12, 2),
                    "opex_monthly": round(opex_total, 2),
                    "incidents": len(tickets),
                    "active_alerts": sum(1 for d in devices if d.get('status') != 'online')
                },
                "financials": {
                    "months": ['Promedio'],
                    "sales": [round(sales_total, 2)],
                    "maintenance": [round(opex_total, 2)]
                }
            }
            
            logger.debug(f"📊 Overview calculado: CAPEX=${capex_total}, OPEX=${opex_total}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error en get_financial_overview: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    def get_device_detail(self, device_id):
        try:
            logger.debug(f"🔍 Obteniendo detalle para dispositivo: {device_id}")
            
            # 1. Obtener datos financieros
            fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            
            if not fin_resp.data:
                logger.warning(f"⚠️  No se encontraron datos financieros para {device_id}")
                finance_row = {}
            else:
                finance_row = fin_resp.data[0]
                logger.debug(f"📋 Datos financieros encontrados: {len(finance_row)} campos")
            
            # 2. Obtener tickets
            tic_resp = self.client.table("tickets").select("*").eq("sitio", device_id).execute()
            tickets = tic_resp.data if tic_resp.data else []
            
            # 3. Obtener datos del dispositivo
            dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            
            if not dev_resp.data:
                logger.error(f"❌ Dispositivo {device_id} no encontrado en tabla devices")
                dev_data = {"device_id": device_id, "status": "not_found"}
            else:
                dev_data = dev_resp.data[0]
                logger.debug(f"📱 Datos dispositivo: {dev_data.get('status', 'unknown')}")
            
            # 4. Calcular totales
            capex = 0.0
            opex = 0.0
            revenue = 0.0
            
            # Sumar CAPEX
            if finance_row:
                capex_keys = [k for k in finance_row.keys() if k.startswith('capex_')]
                for k in capex_keys:
                    capex += self._safe_float(finance_row.get(k))
                
                # Sumar OPEX mensual
                opex_keys = [k for k in finance_row.keys() if k.startswith('opex_') and 'annual' not in k]
                for k in opex_keys:
                    opex += self._safe_float(finance_row.get(k))
                
                # Licencia anual
                license_annual = self._safe_float(finance_row.get('opex_license_annual', 0))
                opex += (license_annual / 12)
                
                # Ventas
                revenue = self._safe_float(finance_row.get('revenue_monthly', 0))
            
            # 5. Calcular ROI
            margin = revenue - opex
            roi = (capex / margin) if margin > 0 and capex > 0 else 0
            
            result = {
                "device": dev_data,
                "financials": finance_row,
                "totals": {
                    "capex": round(capex, 2),
                    "opex": round(opex, 2),
                    "revenue": round(revenue, 2),
                    "margin": round(margin, 2),
                    "roi": round(roi, 2)
                },
                "history": {"tickets": tickets},
                "eco": self._calculate_eco_impact()
            }
            
            logger.debug(f"✅ Detalle obtenido: CAPEX=${capex}, OPEX=${opex}, Revenue=${revenue}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error en get_device_detail para {device_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "error": str(e),
                "device": {"device_id": device_id, "status": "error"},
                "financials": {},
                "totals": {"capex": 0, "opex": 0, "revenue": 0, "margin": 0, "roi": 0},
                "history": {"tickets": []},
                "eco": self._calculate_eco_impact()
            }

    def save_device_financials(self, payload):
        """
        Guarda la configuración financiera.
        """
        try:
            logger.info(f"💾 Iniciando guardado para device_id: {payload.get('device_id')}")
            logger.debug(f"📦 Payload recibido: {payload}")
            
            # Validación básica
            device_id = payload.get('device_id')
            if not device_id:
                logger.error("❌ device_id es requerido")
                return False, "device_id es requerido"
            
            # Limpiar y preparar datos
            cleaned_payload = {"device_id": device_id}
            
            # Lista de columnas válidas
            valid_columns = [
                # CAPEX
                'capex_screen', 'capex_civil', 'capex_structure', 'capex_electrical',
                'capex_meter', 'capex_data_install', 'capex_nuc', 'capex_ups',
                'capex_sending', 'capex_processor', 'capex_modem_wifi', 'capex_modem_sim',
                'capex_teltonika', 'capex_hdmi', 'capex_camera', 'capex_crew',
                'capex_logistics', 'capex_legal', 'capex_first_install', 'capex_admin_qtm',
                # OPEX
                'opex_light', 'opex_internet', 'opex_rent', 'opex_soil_use',
                'opex_license_annual', 'opex_content_scheduling', 'opex_srd',
                # Mantenimiento
                'maint_prev_bimonthly', 'maint_cleaning_supplies', 'maint_gas',
                'maint_corr_parts', 'maint_corr_labor',
                # Ciclo de vida
                'life_retirement', 'life_renewal', 'life_special',
                # Ventas
                'revenue_monthly'
            ]
            
            # Solo incluir columnas válidas y convertir a float
            for key in valid_columns:
                if key in payload:
                    try:
                        value = payload[key]
                        if value is None or value == '':
                            cleaned_payload[key] = 0.0
                        else:
                            cleaned_payload[key] = float(value)
                    except (ValueError, TypeError):
                        cleaned_payload[key] = 0.0
                        logger.warning(f"⚠️  Valor inválido para {key}: {payload[key]}")
            
            # Agregar timestamp
            cleaned_payload['updated_at'] = datetime.now().isoformat()
            
            logger.debug(f"🧹 Payload limpiado: {cleaned_payload}")
            
            # Verificar que el dispositivo existe
            dev_check = self.client.table("devices").select("device_id").eq("device_id", device_id).execute()
            if not dev_check.data:
                logger.warning(f"⚠️  Dispositivo {device_id} no existe en tabla devices, pero se procederá igual")
            
            # Ejecutar UPSERT
            logger.info(f"🔄 Ejecutando UPSERT en tabla 'finances'...")
            result = self.client.table("finances").upsert(cleaned_payload, on_conflict="device_id").execute()
            
            logger.info(f"✅ Guardado exitoso para {device_id}")
            logger.debug(f"📄 Resultado: {result.data}")
            return True, "Guardado exitoso"
            
        except Exception as e:
            logger.error(f"❌ Error crítico en save_device_financials: {str(e)}")
            logger.error(traceback.format_exc())
            return False, str(e)
    
    def init_database(self):
        """
        Inicializa la base de datos con las tablas necesarias.
        Solo ejecutar una vez.
        """
        try:
            logger.info("🛠️  Inicializando base de datos...")
            
            # Verificar si la tabla finances existe
            try:
                self.client.table("finances").select("count", count="exact").limit(1).execute()
                logger.info("✅ Tabla 'finances' ya existe")
            except Exception as e:
                logger.warning(f"⚠️  Tabla 'finances' no existe: {e}")
                # Aquí podrías crear la tabla si fuera necesario
                
            return True, "Base de datos verificada"
            
        except Exception as e:
            logger.error(f"❌ Error inicializando BD: {e}")
            return False, str(e)

# Instancia global del servicio
try:
    supabase = SupabaseService()
    logger.info("✅ SupabaseService inicializado correctamente")
except Exception as e:
    logger.error(f"❌ No se pudo inicializar SupabaseService: {e}")
    supabase = None

@techview_bp.route('/')
def techview_home():
    """Página principal de TechView"""
    try:
        if not supabase:
            return render_template('error.html', error="Servicio de base de datos no disponible"), 500
        
        overview = supabase.get_financial_overview()
        if overview is None:
            overview = {
                "kpis": {"capex": 0, "sales_annual": 0, "opex_monthly": 0, "incidents": 0, "active_alerts": 0},
                "financials": {"months": [], "sales": [], "maintenance": []}
            }
        
        return render_template('techview_dashboard.html', overview=overview)
    except Exception as e:
        logger.error(f"❌ Error en techview_home: {e}")
        return render_template('error.html', error=str(e)), 500

@techview_bp.route('/management')
def techview_management():
    """Página de gestión de costos"""
    try:
        device_id = request.args.get('device_id', '')
        if not device_id:
            return "device_id es requerido", 400
        
        logger.info(f"📱 Cargando página de gestión para: {device_id}")
        return render_template('techview_management.html', device_id=device_id)
    except Exception as e:
        logger.error(f"❌ Error en techview_management: {e}")
        return render_template('error.html', error=str(e)), 500

@techview_bp.route('/analysis')
def techview_analysis():
    """Página de análisis visual"""
    try:
        device_id = request.args.get('device_id', '')
        return render_template('techview_analysis.html', device_id=device_id)
    except Exception as e:
        logger.error(f"❌ Error en techview_analysis: {e}")
        return render_template('error.html', error=str(e)), 500

# ========== API ENDPOINTS ==========

@techview_bp.route('/api/overview')
def api_overview():
    """API: Obtener overview financiero"""
    try:
        if not supabase:
            return jsonify({"error": "Servicio no disponible"}), 503
        
        overview = supabase.get_financial_overview()
        if overview:
            return jsonify(overview)
        else:
            return jsonify({"error": "No se pudo obtener el overview"}), 500
    except Exception as e:
        logger.error(f"❌ Error en api_overview: {e}")
        return jsonify({"error": str(e)}), 500

@techview_bp.route('/api/device/<device_id>')
def api_device_detail(device_id):
    """API: Obtener detalle del dispositivo"""
    try:
        if not supabase:
            return jsonify({"error": "Servicio no disponible"}), 503
        
        logger.info(f"📡 API llamada para dispositivo: {device_id}")
        detail = supabase.get_device_detail(device_id)
        
        if detail and "error" not in detail:
            return jsonify(detail)
        else:
            error_msg = detail.get("error", "Error desconocido") if detail else "No se pudo obtener detalle"
            return jsonify({"error": error_msg}), 500
    except Exception as e:
        logger.error(f"❌ Error en api_device_detail: {e}")
        return jsonify({"error": str(e)}), 500

@techview_bp.route('/api/save', methods=['POST'])
def api_save_financials():
    """API: Guardar datos financieros"""
    try:
        if not supabase:
            return jsonify({"error": "Servicio no disponible"}), 503
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400
        
        logger.info(f"💾 API Save llamada con datos: {list(data.keys())}")
        
        success, message = supabase.save_device_financials(data)
        
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 500
    except Exception as e:
        logger.error(f"❌ Error en api_save_financials: {e}")
        return jsonify({"error": str(e)}), 500

@techview_bp.route('/api/init-db', methods=['POST'])
def api_init_db():
    """API: Inicializar base de datos (solo desarrollo)"""
    try:
        if not supabase:
            return jsonify({"error": "Servicio no disponible"}), 503
        
        success, message = supabase.init_database()
        
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 500
    except Exception as e:
        logger.error(f"❌ Error en api_init_db: {e}")
        return jsonify({"error": str(e)}), 500

@techview_bp.route('/api/test')
def api_test():
    """API: Endpoint de prueba"""
    try:
        if not supabase:
            return jsonify({"status": "error", "message": "Supabase no inicializado"}), 503
        
        # Prueba simple
        test_result = supabase.client.table("finances").select("count", count="exact").limit(1).execute()
        
        return jsonify({
            "status": "success",
            "message": "Conexión exitosa",
            "tables": {
                "finances": test_result.count if hasattr(test_result, 'count') else len(test_result.data)
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Error en api_test: {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

# ========== SQL INITIALIZATION ==========

def run_sql_initialization():
    """
    Ejecuta las sentencias SQL de inicialización.
    Debe llamarse manualmente o al iniciar la aplicación en desarrollo.
    """
    try:
        if not supabase:
            logger.error("❌ No se puede ejecutar SQL: Supabase no inicializado")
            return
        
        logger.info("🛠️  Ejecutando inicialización SQL...")
        
        sql_statements = [
            # 1. Limpiar duplicados existentes
            """
            DELETE FROM finances 
            WHERE id NOT IN (
                SELECT MAX(id) 
                FROM finances 
                GROUP BY device_id
            );
            """,
            
            # 2. Asegurar que device_id sea único
            """
            ALTER TABLE finances DROP CONSTRAINT IF EXISTS finances_device_id_key;
            """,
            """
            ALTER TABLE finances ADD CONSTRAINT finances_device_id_unique UNIQUE (device_id);
            """,
            
            # 3. Crear columnas CAPEX
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_screen NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_civil NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS capex_structure NUMERIC DEFAULT 0;",
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
            
            # 4. Crear columnas OPEX
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_light NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_internet NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_rent NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_soil_use NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_license_annual NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_content_scheduling NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS opex_srd NUMERIC DEFAULT 0;",
            
            # 5. Crear columnas Mantenimiento
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS maint_prev_bimonthly NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS maint_cleaning_supplies NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS maint_gas NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS maint_corr_parts NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS maint_corr_labor NUMERIC DEFAULT 0;",
            
            # 6. Crear columnas Ciclo de Vida
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS life_retirement NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS life_renewal NUMERIC DEFAULT 0;",
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS life_special NUMERIC DEFAULT 0;",
            
            # 7. Crear columnas Ventas
            "ALTER TABLE finances ADD COLUMN IF NOT EXISTS revenue_monthly NUMERIC DEFAULT 0;",
        ]
        
        # Ejecutar cada sentencia SQL
        for i, sql in enumerate(sql_statements):
            try:
                logger.debug(f"  [{i+1}/{len(sql_statements)}] Ejecutando: {sql[:50]}...")
                result = supabase.client.rpc('exec_sql', {'query': sql}).execute()
                logger.debug(f"    ✅ Sentencia ejecutada")
            except Exception as e:
                logger.warning(f"    ⚠️  Error ejecutando sentencia {i+1}: {e}")
                # Continuar con las siguientes
        
        logger.info("✅ Inicialización SQL completada")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en run_sql_initialization: {e}")
        return False

# Inicializar al importar (solo en desarrollo)
if os.environ.get('FLASK_ENV') == 'development':
    logger.info("🚀 Entorno de desarrollo detectado")
    # run_sql_initialization()  # Descomentar si necesitas ejecutar el SQL
