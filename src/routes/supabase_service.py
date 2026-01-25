import os
import logging
import traceback
import re
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from supabase import create_client, Client
from urllib.parse import unquote

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Bluepoint para TechView - DIFERENTE al API principal
techview_bp = Blueprint('techview', __name__, url_prefix='/techview')

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
                raise ValueError("Credenciales de Supabase no configuradas")
            
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
    
    # Métodos requeridos por monitor_service
    def buffer_metric(self, *args, **kwargs):
        logger.debug(f"buffer_metric: {args}, {kwargs}")
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
    
    # Métodos para TechView
    def _safe_float(self, value):
        try:
            if value is None or value == '':
                return 0.0
            return float(value)
        except:
            return 0.0
    
    def get_device_detail(self, device_id):
        try:
            clean_id = clean_device_id(device_id)
            logger.info(f"🔍 TechView buscando dispositivo: {clean_id}")
            
            # Obtener dispositivo
            try:
                dev_resp = self.client.table("devices").select("*").eq("device_id", clean_id).execute()
                device_data = dev_resp.data[0] if dev_resp.data else {
                    "device_id": clean_id,
                    "status": "active",
                    "location": clean_id
                }
            except:
                device_data = {"device_id": clean_id, "status": "unknown"}
            
            # Obtener finanzas
            try:
                fin_resp = self.client.table("finances").select("*").eq("device_id", clean_id).execute()
                finance_data = fin_resp.data[0] if fin_resp.data else {}
            except Exception as e:
                logger.warning(f"⚠️ TechView error obteniendo finanzas: {e}")
                finance_data = {}
            
            # Calcular totales
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
                    elif key == 'amount' and finance_data.get('category') == 'capex':
                        capex += self._safe_float(value)
                    elif key == 'amount' and finance_data.get('category') == 'opex':
                        opex += self._safe_float(value)
                    elif key == 'amount' and finance_data.get('category') == 'revenue':
                        revenue += self._safe_float(value)
            
            margin = revenue - opex
            roi = (capex / margin) if margin > 0 and capex > 0 else 0
            
            return {
                "device": device_data,
                "financials": finance_data,
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
            logger.error(f"❌ TechView error get_device_detail: {e}")
            return {
                "error": str(e),
                "device": {"device_id": device_id, "status": "error"},
                "financials": {},
                "totals": {"capex": 0, "opex": 0, "revenue": 0, "margin": 0, "roi": 0},
                "history": {"tickets": []},
                "eco": {"kwh_saved": 0, "co2_tons": 0, "trees": 0, "efficiency_gain": "0%"}
            }
    
    def save_device_financials(self, payload):
        """Guardar datos para TechView"""
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
                "category": payload.get('category', 'capex'),
                "concept": payload.get('concept', 'techview_save'),
                "updated_at": datetime.now().isoformat()
            }
            
            # Lista de campos
            all_fields = [
                'location', 'type', 'subtype', 'description', 'amount', 'date',
                'recurrence', 'status',
                'capex_screen', 'capex_civil', 'capex_structure', 'capex_electrical',
                'capex_meter', 'capex_data_install', 'capex_nuc', 'capex_ups',
                'capex_sending', 'capex_processor', 'capex_modem_wifi', 'capex_modem_sim',
                'capex_teltonika', 'capex_hdmi', 'capex_camera', 'capex_crew',
                'capex_logistics', 'capex_legal', 'capex_first_install', 'capex_admin_qtm',
                'opex_light', 'opex_internet', 'opex_rent', 'opex_soil_use',
                'opex_license_annual', 'opex_content_scheduling', 'opex_srd',
                'maint_prev_bimonthly', 'maint_cleaning_supplies', 'maint_gas',
                'maint_corr_parts', 'maint_corr_labor', 'maint_corr_gas',
                'life_retirement', 'life_renewal', 'life_special',
                'revenue_monthly'
            ]
            
            # Solo agregar campos que existen en el payload
            for field in all_fields:
                if field in payload and payload[field] not in [None, '']:
                    if field in ['amount', 'revenue_monthly'] or field.startswith(('capex_', 'opex_', 'maint_', 'life_')):
                        try:
                            data_to_save[field] = float(payload[field])
                        except:
                            data_to_save[field] = 0.0
                    else:
                        data_to_save[field] = str(payload[field])
            
            # Calcular amount total si tenemos valores
            total_amount = 0
            for field in data_to_save:
                if field.startswith(('capex_', 'opex_', 'maint_', 'life_')) and isinstance(data_to_save[field], (int, float)):
                    total_amount += data_to_save[field]
            
            if total_amount > 0:
                data_to_save['amount'] = total_amount
            
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

# Instancia global para TechView
techview_service = None
try:
    techview_service = TechViewService()
    logger.info("✅ TechViewService inicializado")
except Exception as e:
    logger.error(f"❌ No se pudo inicializar TechViewService: {e}")

# ============================================
# RUTAS TECHVIEW - TODAS EMPIEZAN CON /techview/
# ============================================

@techview_bp.route('/')
def techview_index():
    return """
    <html>
    <head><title>TechView</title></head>
    <body style="padding: 20px; font-family: Arial;">
        <h1>🚀 TechView - Sistema Financiero</h1>
        <p>Módulo de gestión financiera de dispositivos</p>
        
        <h3>🔗 Enlaces:</h3>
        <ul>
            <li><a href="/techview/diagnostic">Diagnóstico</a></li>
            <li><a href="/techview/management?device_id=TEST_DEVICE">Gestión (Ejemplo)</a></li>
        </ul>
        
        <h3>📊 Estado:</h3>
        <p>TechView Service: {}</p>
        <p>Hora: {}</p>
    </body>
    </html>
    """.format(
        "✅ Conectado" if techview_service else "❌ Desconectado",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@techview_bp.route('/diagnostic')
def techview_diagnostic():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TechView - Diagnóstico</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            .card { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
            button { background: #007bff; color: white; border: none; padding: 10px; margin: 5px; cursor: pointer; }
            pre { background: #333; color: white; padding: 10px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>🔧 TechView - Diagnóstico</h1>
        
        <div class="card">
            <h3>Estado: <span id="status">{}</span></h3>
        </div>
        
        <div class="card">
            <h3>Pruebas</h3>
            <button onclick="testDB()">Test Base de Datos</button>
            <button onclick="testDevice()">Test Device MX_CM_EV...</button>
            <div id="results"></div>
        </div>
        
        <script>
            function testDB() {
                document.getElementById('results').innerHTML = '<p>Probando...</p>';
                fetch('/techview/api/test')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('results').innerHTML = 
                            '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                    })
                    .catch(e => {
                        document.getElementById('results').innerHTML = 
                            '<p style="color: red;">Error: ' + e + '</p>';
                    });
            }
            
            function testDevice() {
                document.getElementById('results').innerHTML = '<p>Consultando...</p>';
                const deviceId = "MX_CM_EV_MGP_01_3591 Calle Arquímedes 173 :238";
                fetch('/techview/api/device/' + encodeURIComponent(deviceId))
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('results').innerHTML = 
                            '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                    })
                    .catch(e => {
                        document.getElementById('results').innerHTML = 
                            '<p style="color: red;">Error: ' + e + '</p>';
                    });
            }
        </script>
    </body>
    </html>
    """.format("✅ Conectado" if techview_service else "❌ Desconectado")

@techview_bp.route('/management')
def techview_management():
    device_id = request.args.get('device_id', '')
    if not device_id:
        return "device_id es requerido", 400
    
    device_id = unquote(device_id)
    return render_template('techview_management.html', device_id=device_id)

# ============================================
# API ENDPOINTS TECHVIEW - TODAS EMPIEZAN CON /techview/api/
# ============================================

@techview_bp.route('/api/test')
def techview_api_test():
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
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@techview_bp.route('/api/device/<path:device_id>')
def techview_api_device(device_id):
    if not techview_service:
        return jsonify({"error": "TechView Service no disponible"}), 503
    
    try:
        data = techview_service.get_device_detail(device_id)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@techview_bp.route('/api/save', methods=['POST'])
def techview_api_save():
    logger.info("=" * 50)
    logger.info("📤 TECHVIEW API SAVE - INICIO")
    
    if not techview_service:
        logger.error("❌ TechView Service no disponible")
        return jsonify({"error": "TechView Service no disponible"}), 503
    
    try:
        if not request.is_json:
            logger.error("❌ No es JSON")
            return jsonify({"error": "Content-Type debe ser application/json"}), 400
        
        data = request.get_json()
        logger.info(f"📦 Datos recibidos. Keys: {list(data.keys())}")
        logger.info(f"📦 Device ID: {data.get('device_id', 'NO PROPORCIONADO')}")
        
        if 'device_id' not in data:
            logger.error("❌ device_id faltante")
            return jsonify({"error": "device_id es requerido"}), 400
        
        success, message = techview_service.save_device_financials(data)
        
        logger.info(f"💾 Resultado: {success} - {message}")
        logger.info("=" * 50)
        
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

# Favicon
@techview_bp.route('/favicon.ico')
def favicon():
    from flask import Response
    return Response(status=204)
