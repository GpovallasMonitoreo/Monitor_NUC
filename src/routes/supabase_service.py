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
            
            # Test de conexión
            test = self.client.table("finances").select("count", count="exact").limit(1).execute()
            logger.info(f"✅ Conexión a Supabase exitosa")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando Supabase: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _safe_float(self, value):
        try:
            return float(value) if value is not None and value != '' else 0.0
        except (ValueError, TypeError):
            return 0.0

    def get_device_detail(self, device_id):
        try:
            # Limpiar device_id
            clean_id = clean_device_id(device_id)
            logger.debug(f"🔍 Buscando dispositivo: '{clean_id}' (original: '{device_id}')")
            
            # 1. Buscar en devices
            dev_resp = self.client.table("devices").select("*").eq("device_id", clean_id).execute()
            
            if not dev_resp.data:
                logger.warning(f"⚠️  Device '{clean_id}' no encontrado en tabla devices")
                # Intentar buscar sin limpiar (por si ya existe con caracteres especiales)
                dev_resp = self.client.table("devices").select("*").eq("device_id", device_id).execute()
                
            if not dev_resp.data:
                # Si aún no existe, crear uno temporal
                dev_data = {
                    "device_id": clean_id,
                    "status": "not_found_in_db",
                    "location": clean_id.split('\t')[-1] if '\t' in clean_id else clean_id
                }
                logger.info(f"📝 Creando registro temporal para device: {clean_id}")
            else:
                dev_data = dev_resp.data[0]
                logger.debug(f"📱 Device encontrado: {dev_data.get('status', 'unknown')}")
            
            # 2. Buscar datos financieros
            fin_resp = self.client.table("finances").select("*").eq("device_id", clean_id).execute()
            
            if not fin_resp.data:
                # Intentar buscar con el ID original
                fin_resp = self.client.table("finances").select("*").eq("device_id", device_id).execute()
                
            finance_row = fin_resp.data[0] if fin_resp.data else {}
            
            # 3. Calcular totales
            capex = 0.0
            opex = 0.0
            revenue = 0.0
            
            if finance_row:
                # Sumar CAPEX
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
                "history": {"tickets": []},
                "eco": {
                    "kwh_saved": 3500,
                    "co2_tons": 1.5,
                    "trees": 75,
                    "efficiency_gain": "66%"
                }
            }
            
            logger.debug(f"✅ Datos obtenidos para {clean_id}")
            return result
            
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
        """
        Guarda la configuración financiera con manejo robusto de device_id.
        """
        try:
            logger.info(f"💾 Iniciando guardado para device_id: {payload.get('device_id')}")
            
            # Validación básica
            raw_device_id = payload.get('device_id')
            if not raw_device_id:
                logger.error("❌ device_id es requerido")
                return False, "device_id es requerido"
            
            # Limpiar device_id
            clean_id = clean_device_id(raw_device_id)
            logger.debug(f"🔄 Device_id limpiado: '{clean_id}' (original: '{raw_device_id}')")
            
            # Verificar/crear en tabla devices primero
            try:
                dev_check = self.client.table("devices").select("device_id").eq("device_id", clean_id).execute()
                
                if not dev_check.data:
                    logger.info(f"📝 Creando registro en tabla 'devices' para: {clean_id}")
                    # Crear registro en devices
                    self.client.table("devices").upsert({
                        "device_id": clean_id,
                        "status": "active",
                        "location": clean_id.split('\t')[-1] if '\t' in clean_id else clean_id,
                        "updated_at": datetime.now().isoformat()
                    }).execute()
            except Exception as e:
                logger.warning(f"⚠️  Error verificando devices: {e}")
            
            # Preparar datos para finances
            cleaned_payload = {"device_id": clean_id}
            
            # Lista de columnas válidas
            valid_columns = [
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
            
            # Solo incluir columnas válidas
            for key in valid_columns:
                if key in payload:
                    try:
                        value = payload[key]
                        cleaned_payload[key] = float(value) if value not in [None, ''] else 0.0
                    except (ValueError, TypeError):
                        cleaned_payload[key] = 0.0
            
            # Agregar timestamp
            cleaned_payload['updated_at'] = datetime.now().isoformat()
            
            logger.debug(f"📤 Insertando/actualizando en finances: {cleaned_payload}")
            
            # Ejecutar UPSERT
            result = self.client.table("finances").upsert(cleaned_payload, on_conflict="device_id").execute()
            
            logger.info(f"✅ Guardado exitoso para {clean_id}")
            return True, "Guardado exitoso"
            
        except Exception as e:
            logger.error(f"❌ Error en save_device_financials: {str(e)}")
            logger.error(traceback.format_exc())
            return False, str(e)

# Instancia global
try:
    supabase = SupabaseService()
except Exception as e:
    logger.error(f"❌ No se pudo inicializar SupabaseService: {e}")
    supabase = None

# ========== ROUTES ==========

@techview_bp.route('/management')
def techview_management():
    """Página de gestión de costos"""
    try:
        device_id = request.args.get('device_id', '')
        if not device_id:
            return "device_id es requerido", 400
        
        # Decodificar URL si es necesario
        from urllib.parse import unquote
        device_id = unquote(device_id)
        
        logger.info(f"📱 Cargando página de gestión para: {device_id}")
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
        
        logger.info(f"📡 API llamada para dispositivo: {device_id}")
        detail = supabase.get_device_detail(device_id)
        
        return jsonify(detail)
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
        
        logger.info(f"💾 API Save llamada")
        
        success, message = supabase.save_device_financials(data)
        
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 500
    except Exception as e:
        logger.error(f"❌ Error en api_save_financials: {e}")
        return jsonify({"error": str(e)}), 500

@techview_bp.route('/api/test-db')
def api_test_db():
    """API: Probar conexión a base de datos"""
    try:
        if not supabase:
            return jsonify({"status": "error", "message": "Supabase no inicializado"}), 503
        
        # Probar varias operaciones
        results = {}
        
        # 1. Contar registros en finances
        try:
            fin_count = supabase.client.table("finances").select("count", count="exact").execute()
            results["finances_count"] = fin_count.count
        except Exception as e:
            results["finances_error"] = str(e)
        
        # 2. Contar registros en devices
        try:
            dev_count = supabase.client.table("devices").select("count", count="exact").execute()
            results["devices_count"] = dev_count.count
        except Exception as e:
            results["devices_error"] = str(e)
        
        # 3. Probar inserción de prueba
        test_id = f"TEST_{datetime.now().timestamp()}"
        try:
            test_data = {
                "device_id": test_id,
                "capex_screen": 1000,
                "revenue_monthly": 500,
                "updated_at": datetime.now().isoformat()
            }
            supabase.client.table("finances").upsert(test_data, on_conflict="device_id").execute()
            results["test_insert"] = "success"
            
            # Limpiar
            supabase.client.table("finances").delete().eq("device_id", test_id).execute()
        except Exception as e:
            results["test_insert_error"] = str(e)
        
        return jsonify({
            "status": "success",
            "results": results,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Error en api_test_db: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@techview_bp.route('/api/create-tables', methods=['POST'])
def api_create_tables():
    """API: Crear tablas necesarias (solo desarrollo)"""
    try:
        if not supabase:
            return jsonify({"error": "Servicio no disponible"}), 503
        
        # SQL para crear tablas básicas
        sql_commands = [
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
            """
            CREATE TABLE IF NOT EXISTS finances (
                id BIGSERIAL PRIMARY KEY,
                device_id TEXT UNIQUE,
                capex_screen NUMERIC DEFAULT 0,
                capex_civil NUMERIC DEFAULT 0,
                capex_structure NUMERIC DEFAULT 0,
                capex_electrical NUMERIC DEFAULT 0,
                capex_meter NUMERIC DEFAULT 0,
                capex_data_install NUMERIC DEFAULT 0,
                capex_nuc NUMERIC DEFAULT 0,
                capex_ups NUMERIC DEFAULT 0,
                capex_sending NUMERIC DEFAULT 0,
                capex_processor NUMERIC DEFAULT 0,
                capex_modem_wifi NUMERIC DEFAULT 0,
                capex_modem_sim NUMERIC DEFAULT 0,
                capex_teltonika NUMERIC DEFAULT 0,
                capex_hdmi NUMERIC DEFAULT 0,
                capex_camera NUMERIC DEFAULT 0,
                capex_crew NUMERIC DEFAULT 0,
                capex_logistics NUMERIC DEFAULT 0,
                capex_legal NUMERIC DEFAULT 0,
                capex_first_install NUMERIC DEFAULT 0,
                capex_admin_qtm NUMERIC DEFAULT 0,
                opex_light NUMERIC DEFAULT 0,
                opex_internet NUMERIC DEFAULT 0,
                opex_rent NUMERIC DEFAULT 0,
                opex_soil_use NUMERIC DEFAULT 0,
                opex_license_annual NUMERIC DEFAULT 0,
                opex_content_scheduling NUMERIC DEFAULT 0,
                opex_srd NUMERIC DEFAULT 0,
                maint_prev_bimonthly NUMERIC DEFAULT 0,
                maint_cleaning_supplies NUMERIC DEFAULT 0,
                maint_gas NUMERIC DEFAULT 0,
                maint_corr_parts NUMERIC DEFAULT 0,
                maint_corr_labor NUMERIC DEFAULT 0,
                life_retirement NUMERIC DEFAULT 0,
                life_renewal NUMERIC DEFAULT 0,
                life_special NUMERIC DEFAULT 0,
                revenue_monthly NUMERIC DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_finances_device_id ON finances(device_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);
            """
        ]
        
        results = []
        for i, sql in enumerate(sql_commands):
            try:
                result = supabase.client.rpc('exec_sql', {'query': sql}).execute()
                results.append(f"Comando {i+1}: ✅ Éxito")
            except Exception as e:
                results.append(f"Comando {i+1}: ❌ Error - {str(e)}")
        
        return jsonify({
            "success": True,
            "message": "Tablas creadas/verificadas",
            "results": results
        })
        
    except Exception as e:
        logger.error(f"❌ Error en api_create_tables: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== Página de diagnóstico ==========

@techview_bp.route('/diagnostic')
def diagnostic_page():
    """Página de diagnóstico de la base de datos"""
    return render_template('diagnostic.html')

if __name__ == "__main__":
    # Ejecutar diagnóstico
    diagnose_database()
