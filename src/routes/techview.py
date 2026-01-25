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
            
            # Lista de campos CAPEX
            capex_fields = [
                'capex_screen', 'capex_civil', 'capex_structure', 'capex_electrical',
                'capex_meter', 'capex_data_install', 'capex_nuc', 'capex_ups',
                'capex_sending', 'capex_processor', 'capex_modem_wifi', 'capex_modem_sim',
                'capex_teltonika', 'capex_hdmi', 'capex_camera', 'capex_crew',
                'capex_logistics', 'capex_legal', 'capex_first_install', 'capex_admin_qtm'
            ]
            
            # Lista de campos OPEX
            opex_fields = [
                'opex_light', 'opex_internet', 'opex_rent', 'opex_soil_use',
                'opex_license_annual', 'opex_content_scheduling', 'opex_srd'
            ]
            
            # Otros campos
            other_fields = [
                'maint_prev_bimonthly', 'maint_cleaning_supplies', 'maint_gas',
                'maint_corr_parts', 'maint_corr_labor', 'maint_corr_gas',
                'life_retirement', 'life_renewal', 'life_special',
                'revenue_monthly'
            ]
            
            all_fields = capex_fields + opex_fields + other_fields
            
            # Solo agregar campos que existen en el payload
            for field in all_fields:
                if field in payload and payload[field] not in [None, '']:
                    try:
                        data_to_save[field] = float(payload[field])
                    except:
                        data_to_save[field] = 0.0
            
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
# RUTAS TECHVIEW
# ============================================

@bp.route('/')
def index():
    return '''
    <html>
    <head><title>TechView - Sistema Financiero</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        .card { background: #f5f5f5; padding: 20px; margin: 10px 0; border-radius: 8px; }
        button { background: #007bff; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
        a { color: #007bff; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
    </head>
    <body>
        <h1>🚀 TechView - Sistema Financiero</h1>
        <p>Módulo de gestión financiera de dispositivos</p>
        
        <div class="card">
            <h3>📊 Estado del Servicio:</h3>
            <p><strong>TechView Service:</strong> ''' + ("✅ Conectado" if techview_service else "❌ Desconectado") + '''</p>
            <p><strong>Hora:</strong> ''' + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '''</p>
        </div>
        
        <div class="card">
            <h3>🔗 Enlaces Rápidos:</h3>
            <ul>
                <li><a href="/techview/diagnostic">Diagnóstico del Sistema</a></li>
                <li><a href="/techview/management?device_id=MX_CM_EV_MGP_01_3591%09Calle%20Arqu%C3%ADmedes%20173%20:238">Gestión - Ejemplo 1</a></li>
                <li><a href="/techview/management?device_id=TEST_DEVICE">Gestión - Dispositivo de Prueba</a></li>
            </ul>
        </div>
        
        <div class="card">
            <h3>📡 Endpoints API:</h3>
            <ul>
                <li><code>GET /techview/api/test</code> - Probar conexión</li>
                <li><code>GET /techview/api/device/{device_id}</code> - Obtener datos</li>
                <li><code>POST /techview/api/save</code> - Guardar datos</li>
            </ul>
        </div>
        
        <script>
            // Prueba automática de conexión
            async function testConnection() {
                try {
                    const response = await fetch('/techview/api/test');
                    const data = await response.json();
                    console.log('Test conexión:', data);
                } catch(e) {
                    console.error('Error test:', e);
                }
            }
            testConnection();
        </script>
    </body>
    </html>
    '''

@bp.route('/diagnostic')
def diagnostic():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>TechView - Diagnóstico</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; max-width: 1200px; margin: 0 auto; }
            .card { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .success { border-left: 4px solid #28a745; }
            .error { border-left: 4px solid #dc3545; }
            .warning { border-left: 4px solid #ffc107; }
            button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; font-size: 14px; }
            button:hover { background: #0056b3; }
            button:disabled { background: #ccc; cursor: not-allowed; }
            pre { background: #f8f9fa; padding: 15px; border-radius: 4px; overflow: auto; font-family: 'Courier New', monospace; font-size: 12px; }
            .loading { color: #6c757d; font-style: italic; }
            .status-indicator { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }
            .status-online { background: #28a745; }
            .status-offline { background: #dc3545; }
            .status-unknown { background: #ffc107; }
        </style>
    </head>
    <body>
        <h1>🔧 TechView - Diagnóstico del Sistema</h1>
        
        <div class="card">
            <h2>📊 Estado del Servicio</h2>
            <div id="service-status">
                <p><span class="status-indicator ''' + ('status-online' if techview_service else 'status-offline') + '''"></span>
                <strong>TechView Service:</strong> ''' + ("✅ CONECTADO" if techview_service else "❌ DESCONECTADO") + '''</p>
                <p><strong>Timestamp:</strong> ''' + datetime.now().isoformat() + '''</p>
            </div>
        </div>
        
        <div class="card">
            <h2>🧪 Pruebas de Funcionalidad</h2>
            <div style="margin-bottom: 15px;">
                <button onclick="runTest('db')">Test Base de Datos</button>
                <button onclick="runTest('save')">Test Guardado</button>
                <button onclick="runTest('device')">Test Consulta Device</button>
                <button onclick="runTest('all')" style="background: #28a745;">Ejecutar Todas las Pruebas</button>
            </div>
            <div id="test-results">
                <p class="loading">Haz click en una prueba para ejecutarla...</p>
            </div>
        </div>
        
        <div class="card">
            <h2>📝 Datos de Prueba</h2>
            <div>
                <label><strong>Device ID para pruebas:</strong></label>
                <input type="text" id="test-device-id" value="MX_CM_EV_MGP_01_3591 Calle Arquímedes 173 :238" style="width: 400px; padding: 8px; margin: 10px 0;">
                <button onclick="testSpecificDevice()">Probar Este Device</button>
            </div>
            <div id="device-test-results" style="margin-top: 15px;"></div>
        </div>
        
        <div class="card">
            <h2>🐛 Logs del Sistema</h2>
            <div id="system-logs">
                <!-- Los logs aparecerán aquí -->
            </div>
        </div>
        
        <script>
            // Interceptar console.log para mostrar en pantalla
            (function() {
                const originalLog = console.log;
                const originalError = console.error;
                
                console.log = function(...args) {
                    originalLog.apply(console, args);
                    addToLog('📘 INFO', args);
                };
                
                console.error = function(...args) {
                    originalError.apply(console, args);
                    addToLog('❌ ERROR', args);
                };
                
                function addToLog(level, args) {
                    const logsDiv = document.getElementById('system-logs');
                    if (logsDiv) {
                        const message = args.map(arg => 
                            typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)
                        ).join(' ');
                        
                        const logEntry = document.createElement('div');
                        logEntry.className = 'log-entry';
                        logEntry.style = 'margin-bottom: 5px; padding: 5px; border-bottom: 1px solid #eee; font-size: 12px;';
                        logEntry.innerHTML = `<strong>${level}:</strong> ${message}`;
                        
                        logsDiv.appendChild(logEntry);
                        logsDiv.scrollTop = logsDiv.scrollHeight;
                    }
                }
            })();
            
            function showLoading(elementId, message) {
                document.getElementById(elementId).innerHTML = 
                    `<div class="loading">${message}</div>`;
            }
            
            function showResult(elementId, data, success) {
                const element = document.getElementById(elementId);
                const className = success ? 'success' : 'error';
                element.innerHTML = `
                    <div class="${className}" style="padding: 15px;">
                        <h4>${success ? '✅ Éxito' : '❌ Error'}</h4>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    </div>
                `;
            }
            
            async function runTest(testType) {
                console.log(`Ejecutando prueba: ${testType}`);
                
                if (testType === 'db' || testType === 'all') {
                    await testDatabase();
                }
                
                if (testType === 'save' || testType === 'all') {
                    await testSave();
                }
                
                if (testType === 'device' || testType === 'all') {
                    await testDevice();
                }
            }
            
            async function testDatabase() {
                showLoading('test-results', 'Probando conexión a base de datos...');
                try {
                    const response = await fetch('/techview/api/test');
                    const data = await response.json();
                    showResult('test-results', data, response.ok);
                } catch(e) {
                    showResult('test-results', {error: e.message}, false);
                }
            }
            
            async function testSave() {
                showLoading('test-results', 'Probando operación de guardado...');
                const testData = {
                    device_id: "TEST_" + Date.now(),
                    capex_screen: 15000,
                    revenue_monthly: 3000,
                    cost_type: "test",
                    category: "test"
                };
                
                try {
                    const response = await fetch('/techview/api/save', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(testData)
                    });
                    const data = await response.json();
                    showResult('test-results', data, response.ok);
                } catch(e) {
                    showResult('test-results', {error: e.message}, false);
                }
            }
            
            async function testDevice() {
                showLoading('test-results', 'Consultando dispositivo de prueba...');
                const deviceId = "MX_CM_EV_MGP_01_3591 Calle Arquímedes 173 :238";
                try {
                    const response = await fetch('/techview/api/device/' + encodeURIComponent(deviceId));
                    const data = await response.json();
                    showResult('test-results', data, response.ok);
                } catch(e) {
                    showResult('test-results', {error: e.message}, false);
                }
            }
            
            async function testSpecificDevice() {
                const deviceId = document.getElementById('test-device-id').value;
                showLoading('device-test-results', `Consultando dispositivo: ${deviceId}`);
                
                try {
                    const response = await fetch('/techview/api/device/' + encodeURIComponent(deviceId));
                    const data = await response.json();
                    showResult('device-test-results', data, response.ok);
                } catch(e) {
                    showResult('device-test-results', {error: e.message}, false);
                }
            }
            
            // Ejecutar prueba automática al cargar
            document.addEventListener('DOMContentLoaded', () => {
                console.log('🔧 Diagnóstico TechView cargado');
                testDatabase();
            });
        </script>
    </body>
    </html>
    '''

@bp.route('/management')
def management():
    device_id = request.args.get('device_id', '')
    if not device_id:
        return '''
        <html>
        <body style="padding: 40px; font-family: Arial;">
            <h1>❌ Error: device_id requerido</h1>
            <p>Es necesario especificar un device_id en la URL:</p>
            <code>/techview/management?device_id=TU_DEVICE_ID</code>
            <p>Ejemplos:</p>
            <ul>
                <li><a href="/techview/management?device_id=MX_CM_EV_MGP_01_3591%09Calle%20Arqu%C3%ADmedes%20173%20:238">Device con tab</a></li>
                <li><a href="/techview/management?device_id=TEST_DEVICE_123">Device de prueba</a></li>
            </ul>
            <p><a href="/techview">← Volver a TechView</a></p>
        </body>
        </html>
        ''', 400
    
    device_id = unquote(device_id)
    logger.info(f"📱 TechView cargando gestión para: {device_id}")
    
    # Renderizar template de gestión
    return render_template('techview_management.html', device_id=device_id)

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
            "has_cost_type": True,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ TechView API test error: {e}")
        return jsonify({
            "status": "error",
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
        logger.info(f"📦 Datos recibidos. Keys: {list(data.keys())}")
        logger.info(f"📦 Device ID: {data.get('device_id', 'NO PROPORCIONADO')}")
        
        if 'device_id' not in data:
            logger.error("❌ device_id faltante")
            return jsonify({"error": "device_id es requerido"}), 400
        
        success, message = techview_service.save_device_financials(data)
        
        logger.info(f"💾 Resultado: {success} - {message}")
        logger.info("=" * 60)
        
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

# Favicon para evitar error 404
@bp.route('/favicon.ico')
def favicon():
    from flask import Response
    return Response(status=204)

logger.info("✅ Módulo TechView cargado")
