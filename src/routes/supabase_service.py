import os
import logging
import traceback
import re
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, render_template, current_app
from supabase import create_client, Client
from typing import Optional, Dict, List, Any
from urllib.parse import unquote

# ============================================
# CONFIGURACIÓN DE LOGGING
# ============================================

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# BLUEPRINT
# ============================================

techview_bp = Blueprint('techview', __name__, url_prefix='/techview')

# ============================================
# FUNCIONES DE UTILIDAD
# ============================================

def clean_device_id(device_id: str) -> str:
    """
    Limpia el device_id de caracteres problemáticos.
    """
    if not device_id:
        return ""
    
    try:
        # Decodificar URL si es necesario
        device_id = unquote(device_id)
    except:
        pass
    
    # Reemplazar tabs por espacios
    device_id = device_id.replace('\t', ' ')
    
    # Remover caracteres de control (ASCII 0-31 y 127)
    device_id = re.sub(r'[\x00-\x1f\x7f]', '', device_id)
    
    # Normalizar espacios múltiples
    device_id = ' '.join(device_id.split())
    
    return device_id.strip()

def format_currency(value: float) -> str:
    """Formatea un valor como moneda"""
    if value == 0:
        return "$0"
    return f"${value:,.2f}"

# ============================================
# CLASE SUPABASE SERVICE COMPLETA
# ============================================

class SupabaseService:
    """
    Servicio completo para manejar operaciones con Supabase.
    Incluye todos los métodos necesarios para compatibilidad.
    """
    
    def __init__(self):
        """Inicializa la conexión con Supabase"""
        try:
            self.url = os.environ.get("SUPABASE_URL")
            self.key = os.environ.get("SUPABASE_KEY")
            
            if not self.url:
                logger.error("❌ SUPRABASE_URL no configurado")
                raise ValueError("SUPABASE_URL no configurado")
            if not self.key:
                logger.error("❌ SUPRABASE_KEY no configurado")
                raise ValueError("SUPABASE_KEY no configurado")
            
            logger.info(f"🔗 Conectando a Supabase: {self.url[:30]}...")
            self.client: Client = create_client(self.url, self.key)
            
            # Test de conexión básico
            self._test_connection()
            
            logger.info("✅ SupabaseService inicializado correctamente")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando SupabaseService: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _test_connection(self):
        """Prueba la conexión con Supabase"""
        try:
            # Intentar con devices primero (tabla más básica)
            test = self.client.table("devices").select("count", count="exact").limit(1).execute()
            logger.info(f"✅ Conexión exitosa. Devices: {test.count}")
            return True
        except Exception as e:
            logger.warning(f"⚠️  No se pudo conectar a devices: {e}")
            try:
                # Intentar con finances
                test = self.client.table("finances").select("count", count="exact").limit(1).execute()
                logger.info(f"✅ Conexión exitosa. Finances: {test.count}")
                return True
            except Exception as e2:
                logger.error(f"❌ No se pudo conectar a ninguna tabla: {e2}")
                raise
    
    def _safe_float(self, value: Any) -> float:
        """Convierte seguro a float"""
        try:
            if value is None or value == '':
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _safe_int(self, value: Any) -> int:
        """Convierte seguro a int"""
        try:
            if value is None or value == '':
                return 0
            return int(value)
        except (ValueError, TypeError):
            return 0
    
    # ============================================
    # MÉTODOS PARA COMPATIBILIDAD CON MONITOR_SERVICE
    # ============================================
    
    def buffer_metric(self, metric_type: str, value: float, device_id: str = None, 
                     tags: Dict = None, timestamp: datetime = None):
        """
        Bufferiza una métrica para posterior envío.
        Método requerido por monitor_service.
        """
        try:
            logger.debug(f"📊 buffer_metric: {metric_type}={value}, device={device_id}")
            
            # Aquí normalmente almacenarías en un buffer para enviar en batch
            # Por ahora, lo enviamos directamente
            return self.log_metric(metric_type, value, device_id, tags, timestamp)
            
        except Exception as e:
            logger.error(f"❌ Error en buffer_metric: {e}")
            return False
    
    def flush_metrics(self):
        """
        Envía todas las métricas en buffer.
        Método requerido por monitor_service.
        """
        try:
            logger.debug("🔄 flush_metrics llamado")
            # En una implementación real, aquí enviarías todas las métricas bufferizadas
            return True
        except Exception as e:
            logger.error(f"❌ Error en flush_metrics: {e}")
            return False
    
    def upsert_device_status(self, device_id: str, status: str, 
                           location: str = None, extra_data: Dict = None) -> bool:
        """
        Actualiza o inserta el estado de un dispositivo.
        Método requerido por monitor_service.
        """
        try:
            clean_id = clean_device_id(device_id)
            logger.info(f"📱 upsert_device_status: {clean_id} -> {status}")
            
            data = {
                "device_id": clean_id,
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
            
            if location:
                data["location"] = location
            
            if extra_data:
                data.update(extra_data)
            
            # Intentar upsert
            result = self.client.table("devices").upsert(data, on_conflict="device_id").execute()
            
            logger.debug(f"✅ Estado actualizado: {clean_id} -> {status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en upsert_device_status: {e}")
            return False
    
    def log_metric(self, metric_type: str, value: float, device_id: str = None,
                  tags: Dict = None, timestamp: datetime = None) -> bool:
        """
        Registra una métrica en la base de datos.
        """
        try:
            metric_data = {
                "type": metric_type,
                "value": value,
                "timestamp": timestamp.isoformat() if timestamp else datetime.now().isoformat()
            }
            
            if device_id:
                metric_data["device_id"] = clean_device_id(device_id)
            
            if tags:
                metric_data["tags"] = json.dumps(tags)
            
            logger.info(f"📈 METRIC: {metric_type}={value}, device={device_id}")
            
            # Intentar guardar en tabla metrics si existe
            try:
                self.client.table("metrics").insert(metric_data).execute()
                logger.debug(f"✅ Métrica guardada en base de datos")
            except Exception as e:
                logger.debug(f"⚠️  No se pudo guardar métrica en BD: {e}")
                # No es crítico, solo logueamos
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en log_metric: {e}")
            return False
    
    def get_device_metrics(self, device_id: str, metric_type: str = None,
                          start_time: datetime = None, end_time: datetime = None) -> List[Dict]:
        """
        Obtiene métricas de un dispositivo.
        """
        try:
            clean_id = clean_device_id(device_id)
            query = self.client.table("metrics").select("*").eq("device_id", clean_id)
            
            if metric_type:
                query = query.eq("type", metric_type)
            
            if start_time:
                query = query.gte("timestamp", start_time.isoformat())
            
            if end_time:
                query = query.lte("timestamp", end_time.isoformat())
            
            result = query.order("timestamp", desc=True).execute()
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"❌ Error en get_device_metrics: {e}")
            return []
    
    # ============================================
    # MÉTODOS PARA TECHVIEW (FINANZAS)
    # ============================================
    
    def get_device_detail(self, device_id: str) -> Dict:
        """
        Obtiene todos los detalles de un dispositivo incluyendo finanzas.
        """
        try:
            clean_id = clean_device_id(device_id)
            logger.info(f"🔍 Obteniendo detalle para: '{clean_id}'")
            
            # 1. Obtener información del dispositivo
            device_data = self._get_device_info(clean_id)
            
            # 2. Obtener información financiera
            finance_data = self._get_finance_info(clean_id)
            
            # 3. Calcular totales y ROI
            totals = self._calculate_totals(finance_data)
            
            # 4. Obtener tickets/historial
            history = self._get_device_history(clean_id)
            
            # 5. Calcular impacto ecológico
            eco_impact = self._calculate_eco_impact(totals)
            
            return {
                "device": device_data,
                "financials": finance_data,
                "totals": totals,
                "history": history,
                "eco": eco_impact,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error en get_device_detail: {e}")
            return self._create_error_response(device_id, str(e))
    
    def _get_device_info(self, device_id: str) -> Dict:
        """Obtiene información del dispositivo"""
        try:
            result = self.client.table("devices").select("*").eq("device_id", device_id).execute()
            
            if result.data:
                device = result.data[0]
                logger.debug(f"📱 Device encontrado: {device.get('status', 'unknown')}")
                return device
            else:
                # Si no existe, crear uno temporal
                logger.info(f"📝 Creando registro temporal para: {device_id}")
                return {
                    "device_id": device_id,
                    "status": "active",
                    "location": device_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.warning(f"⚠️  Error obteniendo device info: {e}")
            return {
                "device_id": device_id,
                "status": "error",
                "error": str(e)
            }
    
    def _get_finance_info(self, device_id: str) -> Dict:
        """Obtiene información financiera"""
        try:
            result = self.client.table("finances").select("*").eq("device_id", device_id).execute()
            
            if result.data:
                finance_data = result.data[0]
                logger.debug(f"💰 Finanzas encontradas: {len(finance_data)} campos")
                return finance_data
            else:
                logger.debug(f"💰 No hay datos financieros para: {device_id}")
                return {}
                
        except Exception as e:
            logger.warning(f"⚠️  Error obteniendo finance info: {e}")
            return {}
    
    def _calculate_totals(self, finance_data: Dict) -> Dict:
        """Calcula totales financieros"""
        try:
            capex = 0.0
            opex = 0.0
            revenue = 0.0
            
            if finance_data:
                # Sumar CAPEX
                for key, value in finance_data.items():
                    if key.startswith('capex_'):
                        capex += self._safe_float(value)
                    elif key.startswith('opex_') and 'annual' not in key:
                        opex += self._safe_float(value)
                    elif key == 'opex_license_annual':
                        opex += (self._safe_float(value) / 12)  # Convertir anual a mensual
                    elif key == 'revenue_monthly':
                        revenue = self._safe_float(value)
            
            margin = revenue - opex
            roi_months = (capex / margin) if margin > 0 and capex > 0 else 0
            
            return {
                "capex": round(capex, 2),
                "opex": round(opex, 2),
                "revenue": round(revenue, 2),
                "margin": round(margin, 2),
                "roi_months": round(roi_months, 2),
                "roi_years": round(roi_months / 12, 2) if roi_months > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculando totales: {e}")
            return {
                "capex": 0,
                "opex": 0,
                "revenue": 0,
                "margin": 0,
                "roi_months": 0,
                "roi_years": 0
            }
    
    def _get_device_history(self, device_id: str) -> Dict:
        """Obtiene historial del dispositivo"""
        try:
            # Buscar tickets
            tickets_result = self.client.table("tickets").select("*").eq("sitio", device_id).execute()
            tickets = tickets_result.data if tickets_result.data else []
            
            # Buscar métricas recientes
            end_time = datetime.now()
            start_time = end_time - timedelta(days=30)
            metrics = self.get_device_metrics(device_id, start_time=start_time, end_time=end_time)
            
            return {
                "tickets": tickets,
                "metrics": metrics,
                "ticket_count": len(tickets),
                "metric_count": len(metrics)
            }
            
        except Exception as e:
            logger.warning(f"⚠️  Error obteniendo historial: {e}")
            return {
                "tickets": [],
                "metrics": [],
                "ticket_count": 0,
                "metric_count": 0
            }
    
    def _calculate_eco_impact(self, totals: Dict) -> Dict:
        """Calcula impacto ecológico"""
        try:
            # Fórmula simplificada basada en consumo eléctrico
            # Asumiendo pantalla LED vs pantalla tradicional
            daily_hours = 18
            days_per_year = 365
            watt_saved_per_hour = 300  # Watts ahorrados (450W tradicional - 150W LED)
            
            kwh_saved = (watt_saved_per_hour * daily_hours * days_per_year) / 1000
            co2_tons = (kwh_saved * 0.45) / 1000  # 0.45 kg CO2 por kWh
            trees_equivalent = int(co2_tons * 50)  # Cada árbol absorbe ~20kg CO2 al año
            
            return {
                "kwh_saved": round(kwh_saved, 0),
                "co2_tons": round(co2_tons, 2),
                "trees": trees_equivalent,
                "efficiency_gain": "66%",
                "daily_savings": round(kwh_saved / 365, 2)
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculando impacto ecológico: {e}")
            return {
                "kwh_saved": 0,
                "co2_tons": 0,
                "trees": 0,
                "efficiency_gain": "0%",
                "daily_savings": 0
            }
    
    def _create_error_response(self, device_id: str, error_msg: str) -> Dict:
        """Crea una respuesta de error"""
        return {
            "error": error_msg,
            "device": {
                "device_id": device_id,
                "status": "error",
                "error": error_msg
            },
            "financials": {},
            "totals": {
                "capex": 0,
                "opex": 0,
                "revenue": 0,
                "margin": 0,
                "roi_months": 0,
                "roi_years": 0
            },
            "history": {
                "tickets": [],
                "metrics": [],
                "ticket_count": 0,
                "metric_count": 0
            },
            "eco": {
                "kwh_saved": 0,
                "co2_tons": 0,
                "trees": 0,
                "efficiency_gain": "0%",
                "daily_savings": 0
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def save_device_financials(self, payload: Dict) -> tuple:
        """
        Guarda los datos financieros de un dispositivo.
        Maneja automáticamente el campo problemático 'cost_type'.
        """
        try:
            logger.info("💾 Iniciando guardado de datos financieros")
            
            # Validación básica
            if not payload or 'device_id' not in payload:
                return False, "device_id es requerido"
            
            raw_device_id = payload['device_id']
            clean_id = clean_device_id(raw_device_id)
            logger.info(f"📝 Guardando para: '{clean_id}'")
            
            # 1. Filtrar y limpiar el payload
            cleaned_payload = self._clean_financial_payload(payload)
            
            # 2. Asegurar que el dispositivo existe
            self._ensure_device_exists(clean_id)
            
            # 3. Guardar datos financieros
            success = self._save_financial_data(clean_id, cleaned_payload)
            
            if success:
                logger.info(f"✅ Guardado exitoso para: {clean_id}")
                return True, "Datos guardados correctamente"
            else:
                return False, "Error al guardar datos financieros"
                
        except Exception as e:
            logger.error(f"❌ Error en save_device_financials: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"Error crítico: {str(e)}"
    
    def _clean_financial_payload(self, payload: Dict) -> Dict:
        """Limpia y valida el payload financiero"""
        cleaned = {"device_id": clean_device_id(payload['device_id'])}
        
        # Lista de campos válidos
        valid_fields = [
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
        
        # Filtrar solo campos válidos y convertir a float
        for field in valid_fields:
            if field in payload:
                cleaned[field] = self._safe_float(payload[field])
        
        # Eliminar campos problemáticos si existen
        if 'cost_type' in payload:
            logger.warning(f"⚠️  Eliminando campo problemático 'cost_type'")
        
        # Agregar timestamp
        cleaned['updated_at'] = datetime.now().isoformat()
        
        logger.debug(f"🧹 Payload limpiado: {list(cleaned.keys())}")
        return cleaned
    
    def _ensure_device_exists(self, device_id: str):
        """Asegura que el dispositivo exista en la tabla devices"""
        try:
            # Verificar si existe
            check = self.client.table("devices").select("device_id").eq("device_id", device_id).execute()
            
            if not check.data:
                # Crear dispositivo si no existe
                logger.info(f"➕ Creando dispositivo: {device_id}")
                self.client.table("devices").insert({
                    "device_id": device_id,
                    "status": "active",
                    "location": device_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }).execute()
                
        except Exception as e:
            logger.warning(f"⚠️  Error asegurando dispositivo: {e}")
    
    def _save_financial_data(self, device_id: str, data: Dict) -> bool:
        """Guarda los datos financieros en la base de datos"""
        try:
            # Intentar upsert
            result = self.client.table("finances").upsert(data, on_conflict="device_id").execute()
            
            if result.data:
                logger.debug(f"📄 Datos guardados: ID={result.data[0].get('id')}")
                return True
            else:
                logger.error("❌ No se recibieron datos de confirmación")
                return False
                
        except Exception as e:
            error_str = str(e)
            logger.error(f"❌ Error guardando datos financieros: {error_str}")
            
            # Verificar si es error de columna faltante
            if "column" in error_str.lower() and "does not exist" in error_str.lower():
                logger.error("⚠️  ERROR: Columna faltante en la tabla 'finances'")
                logger.error("💡 Ejecuta /techview/api/fix-table para agregar columnas faltantes")
            
            return False
    
    # ============================================
    # MÉTODOS DE ADMINISTRACIÓN DE BASE DE DATOS
    # ============================================
    
    def check_database_tables(self) -> Dict:
        """Verifica el estado de las tablas en la base de datos"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "tables": {}
        }
        
        tables_to_check = ['devices', 'finances', 'tickets', 'metrics']
        
        for table in tables_to_check:
            try:
                result = self.client.table(table).select("count", count="exact").limit(1).execute()
                results["tables"][table] = {
                    "exists": True,
                    "count": result.count,
                    "status": "✅ OK"
                }
            except Exception as e:
                error_msg = str(e)
                if "relation" in error_msg and "does not exist" in error_msg:
                    results["tables"][table] = {
                        "exists": False,
                        "count": 0,
                        "status": "❌ NO EXISTE"
                    }
                else:
                    results["tables"][table] = {
                        "exists": "unknown",
                        "count": 0,
                        "status": f"⚠️  ERROR: {error_msg[:100]}"
                    }
        
        return results
    
    def create_basic_tables(self) -> Dict:
        """Crea las tablas básicas si no existen"""
        results = {"operations": []}
        
        # SQL para crear tablas
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
            
            # Tabla finances (versión básica)
            """
            CREATE TABLE IF NOT EXISTS finances (
                id BIGSERIAL PRIMARY KEY,
                device_id TEXT UNIQUE,
                capex_screen NUMERIC DEFAULT 0,
                capex_civil NUMERIC DEFAULT 0,
                capex_structure NUMERIC DEFAULT 0,
                revenue_monthly NUMERIC DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """,
            
            # Índices
            "CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);",
            "CREATE INDEX IF NOT EXISTS idx_finances_device_id ON finances(device_id);"
        ]
        
        for i, sql in enumerate(sql_commands):
            try:
                # En Supabase podemos usar rpc para ejecutar SQL
                self.client.rpc('exec_sql', {'query': sql}).execute()
                results["operations"].append({
                    "sql": i+1,
                    "status": "✅ Éxito",
                    "message": "Tabla/índice creado"
                })
            except Exception as e:
                error_msg = str(e)
                results["operations"].append({
                    "sql": i+1,
                    "status": "❌ Error",
                    "message": error_msg[:200]
                })
        
        return results
    
    def add_missing_columns(self) -> Dict:
        """Agrega columnas faltantes a la tabla finances"""
        results = {"added_columns": [], "errors": []}
        
        # Columnas a agregar si no existen
        columns_to_add = [
            # CAPEX adicional
            ("capex_electrical", "NUMERIC DEFAULT 0"),
            ("capex_meter", "NUMERIC DEFAULT 0"),
            ("capex_data_install", "NUMERIC DEFAULT 0"),
            ("capex_nuc", "NUMERIC DEFAULT 0"),
            ("capex_ups", "NUMERIC DEFAULT 0"),
            ("capex_sending", "NUMERIC DEFAULT 0"),
            ("capex_processor", "NUMERIC DEFAULT 0"),
            ("capex_modem_wifi", "NUMERIC DEFAULT 0"),
            ("capex_modem_sim", "NUMERIC DEFAULT 0"),
            ("capex_teltonika", "NUMERIC DEFAULT 0"),
            ("capex_hdmi", "NUMERIC DEFAULT 0"),
            ("capex_camera", "NUMERIC DEFAULT 0"),
            ("capex_crew", "NUMERIC DEFAULT 0"),
            ("capex_logistics", "NUMERIC DEFAULT 0"),
            ("capex_legal", "NUMERIC DEFAULT 0"),
            ("capex_first_install", "NUMERIC DEFAULT 0"),
            ("capex_admin_qtm", "NUMERIC DEFAULT 0"),
            
            # OPEX
            ("opex_light", "NUMERIC DEFAULT 0"),
            ("opex_internet", "NUMERIC DEFAULT 0"),
            ("opex_rent", "NUMERIC DEFAULT 0"),
            ("opex_soil_use", "NUMERIC DEFAULT 0"),
            ("opex_license_annual", "NUMERIC DEFAULT 0"),
            ("opex_content_scheduling", "NUMERIC DEFAULT 0"),
            ("opex_srd", "NUMERIC DEFAULT 0"),
            
            # Mantenimiento
            ("maint_prev_bimonthly", "NUMERIC DEFAULT 0"),
            ("maint_cleaning_supplies", "NUMERIC DEFAULT 0"),
            ("maint_gas", "NUMERIC DEFAULT 0"),
            ("maint_corr_parts", "NUMERIC DEFAULT 0"),
            ("maint_corr_labor", "NUMERIC DEFAULT 0"),
            
            # Ciclo de vida
            ("life_retirement", "NUMERIC DEFAULT 0"),
            ("life_renewal", "NUMERIC DEFAULT 0"),
            ("life_special", "NUMERIC DEFAULT 0")
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                sql = f"ALTER TABLE finances ADD COLUMN IF NOT EXISTS {column_name} {column_type};"
                self.client.rpc('exec_sql', {'query': sql}).execute()
                results["added_columns"].append(column_name)
                logger.info(f"✅ Columna agregada: {column_name}")
            except Exception as e:
                error_msg = str(e)
                results["errors"].append({
                    "column": column_name,
                    "error": error_msg[:200]
                })
                logger.error(f"❌ Error agregando columna {column_name}: {error_msg}")
        
        return results
    
    def test_save_operation(self) -> Dict:
        """Prueba una operación de guardado"""
        try:
            test_id = f"TEST_{int(datetime.now().timestamp())}"
            test_data = {
                "device_id": test_id,
                "capex_screen": 15000.50,
                "capex_civil": 5000.00,
                "revenue_monthly": 3000.75,
                "updated_at": datetime.now().isoformat()
            }
            
            # Guardar
            result = self.client.table("finances").upsert(test_data, on_conflict="device_id").execute()
            
            # Verificar
            check = self.client.table("finances").select("*").eq("device_id", test_id).execute()
            
            # Limpiar
            self.client.table("finances").delete().eq("device_id", test_id).execute()
            
            return {
                "success": True,
                "test_id": test_id,
                "saved_data": test_data,
                "retrieved_data": check.data[0] if check.data else None,
                "message": "✅ Operación de guardado exitosa"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "❌ Error en operación de guardado"
            }

# ============================================
# INSTANCIA GLOBAL DEL SERVICIO
# ============================================

try:
    supabase_service = SupabaseService()
    logger.info("🚀 SupabaseService inicializado globalmente")
except Exception as e:
    logger.error(f"🔥 ERROR CRÍTICO: No se pudo inicializar SupabaseService: {e}")
    supabase_service = None

# ============================================
# RUTAS DE LA APLICACIÓN
# ============================================

@techview_bp.route('/')
def index():
    """Página principal de TechView"""
    return """
    <html>
    <head><title>TechView - Sistema de Gestión</title></head>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h1>🚀 TechView - Sistema de Gestión</h1>
        <p>Bienvenido al sistema de gestión de dispositivos y finanzas.</p>
        
        <h2>🔧 Herramientas de Diagnóstico:</h2>
        <ul>
            <li><a href="/techview/diagnostic" target="_blank">Diagnóstico Completo</a></li>
            <li><a href="/techview/api/test-db" target="_blank">Probar Conexión BD</a></li>
            <li><a href="/techview/api/check-tables" target="_blank">Verificar Tablas</a></li>
        </ul>
        
        <h2>📊 Gestión:</h2>
        <ul>
            <li><a href="/techview/management?device_id=TEST_DEVICE" target="_blank">Página de Gestión (Ejemplo)</a></li>
            <li><a href="/techview/analysis" target="_blank">Análisis Visual</a></li>
        </ul>
        
        <h2>⚙️ Administración:</h2>
        <ul>
            <li><a href="/techview/api/create-tables" target="_blank">Crear Tablas Básicas</a> (POST)</li>
            <li><a href="/techview/api/fix-table" target="_blank">Reparar Tabla Finances</a> (POST)</li>
        </ul>
        
        <hr>
        <p><strong>Estado del servicio:</strong> {}</p>
        <p><em>Última actualización: {}</em></p>
    </body>
    </html>
    """.format(
        "✅ CONECTADO" if supabase_service else "❌ DESCONECTADO",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@techview_bp.route('/diagnostic')
def diagnostic_page():
    """Página completa de diagnóstico"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TechView - Diagnóstico</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .card { background: #f5f5f5; border-radius: 8px; padding: 20px; margin: 10px 0; }
            .success { background: #d4edda; border-left: 4px solid #28a745; }
            .error { background: #f8d7da; border-left: 4px solid #dc3545; }
            .warning { background: #fff3cd; border-left: 4px solid #ffc107; }
            button { background: #007bff; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; margin: 5px; }
            button:hover { background: #0056b3; }
            pre { background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 5px; overflow: auto; }
            .loading { color: #6c757d; font-style: italic; }
        </style>
    </head>
    <body>
        <h1>🔧 Diagnóstico TechView</h1>
        
        <div class="card">
            <h2>1. Estado del Servicio</h2>
            <div id="service-status" class="loading">Comprobando...</div>
        </div>
        
        <div class="card">
            <h2>2. Base de Datos</h2>
            <button onclick="testDatabase()">Probar Conexión</button>
            <button onclick="checkTables()">Verificar Tablas</button>
            <button onclick="createTables()" style="background: #28a745;">Crear Tablas</button>
            <button onclick="fixTable()" style="background: #ffc107;">Reparar Tabla</button>
            <div id="db-results"></div>
        </div>
        
        <div class="card">
            <h2>3. Probar Guardado</h2>
            <button onclick="testSave()">Probar Operación de Guardado</button>
            <div id="test-results"></div>
        </div>
        
        <div class="card">
            <h2>4. Probar Device Específico</h2>
            <input type="text" id="device-id" value="MX_CM_EV_MGP_01_3591 Calle Arquímedes 173 :238" style="width: 300px; padding: 5px;">
            <button onclick="testDevice()">Probar Device</button>
            <div id="device-results"></div>
        </div>
        
        <script>
            // Estado del servicio
            fetch('/techview/api/service-status')
                .then(r => r.json())
                .then(data => {
                    const statusDiv = document.getElementById('service-status');
                    statusDiv.innerHTML = data.connected ? 
                        '<span style="color: green;">✅ CONECTADO</span>' : 
                        '<span style="color: red;">❌ DESCONECTADO</span>';
                    statusDiv.innerHTML += '<br><small>' + data.message + '</small>';
                });
            
            async function testDatabase() {
                showLoading('db-results', 'Probando conexión...');
                const response = await fetch('/techview/api/test-db');
                const data = await response.json();
                showResult('db-results', data, response.ok);
            }
            
            async function checkTables() {
                showLoading('db-results', 'Verificando tablas...');
                const response = await fetch('/techview/api/check-tables');
                const data = await response.json();
                showResult('db-results', data, response.ok);
            }
            
            async function createTables() {
                if (!confirm('¿Crear tablas básicas? Esto solo debe hacerse una vez.')) return;
                showLoading('db-results', 'Creando tablas...');
                const response = await fetch('/techview/api/create-tables', { method: 'POST' });
                const data = await response.json();
                showResult('db-results', data, response.ok);
            }
            
            async function fixTable() {
                if (!confirm('¿Agregar columnas faltantes a la tabla finances?')) return;
                showLoading('db-results', 'Reparando tabla...');
                const response = await fetch('/techview/api/fix-table', { method: 'POST' });
                const data = await response.json();
                showResult('db-results', data, response.ok);
            }
            
            async function testSave() {
                showLoading('test-results', 'Probando guardado...');
                const response = await fetch('/techview/api/test-save', { method: 'POST' });
                const data = await response.json();
                showResult('test-results', data, response.ok);
            }
            
            async function testDevice() {
                const deviceId = document.getElementById('device-id').value;
                showLoading('device-results', 'Consultando device...');
                const response = await fetch('/techview/api/device/' + encodeURIComponent(deviceId));
                const data = await response.json();
                showResult('device-results', data, response.ok);
            }
            
            function showLoading(elementId, message) {
                document.getElementById(elementId).innerHTML = 
                    '<div class="loading">' + message + '</div>';
            }
            
            function showResult(elementId, data, success) {
                const element = document.getElementById(elementId);
                const className = success ? 'success' : 'error';
                element.innerHTML = `
                    <div class="${className}">
                        <h3>${success ? '✅ Éxito' : '❌ Error'}</h3>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    </div>
                `;
            }
        </script>
    </body>
    </html>
    """

@techview_bp.route('/management')
def management_page():
    """Página de gestión de dispositivos"""
    try:
        device_id = request.args.get('device_id', '')
        if not device_id:
            return """
            <html>
            <body style="padding: 40px; font-family: Arial;">
                <h1>❌ Error: device_id requerido</h1>
                <p>Es necesario especificar un device_id en la URL:</p>
                <code>/techview/management?device_id=TU_DEVICE_ID</code>
                <p><a href="/techview">← Volver al inicio</a></p>
            </body>
            </html>
            """, 400
        
        # Decodificar device_id
        device_id = unquote(device_id)
        logger.info(f"📱 Cargando página de gestión para: {device_id}")
        
        # Renderizar template (asegúrate de tener techview_management.html en templates/)
        return render_template('techview_management.html', device_id=device_id)
        
    except Exception as e:
        logger.error(f"❌ Error en management_page: {e}")
        return f"""
        <html>
        <body style="padding: 40px; font-family: Arial;">
            <h1>❌ Error en página de gestión</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <pre>{traceback.format_exc()}</pre>
            <p><a href="/techview">← Volver al inicio</a></p>
        </body>
        </html>
        """, 500

# ============================================
# API ENDPOINTS
# ============================================

@techview_bp.route('/api/service-status')
def api_service_status():
    """API: Estado del servicio"""
    return jsonify({
        "connected": supabase_service is not None,
        "timestamp": datetime.now().isoformat(),
        "message": "Servicio TechView" + (" ✅" if supabase_service else " ❌")
    })

@techview_bp.route('/api/test-db')
def api_test_db():
    """API: Probar conexión a base de datos"""
    if not supabase_service:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        results = supabase_service.check_database_tables()
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "results": results
        })
    except Exception as e:
        logger.error(f"❌ Error en api_test_db: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@techview_bp.route('/api/check-tables')
def api_check_tables():
    """API: Verificar tablas"""
    if not supabase_service:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        results = supabase_service.check_database_tables()
        return jsonify(results)
    except Exception as e:
        logger.error(f"❌ Error en api_check_tables: {e}")
        return jsonify({"error": str(e)}), 500

@techview_bp.route('/api/create-tables', methods=['POST'])
def api_create_tables():
    """API: Crear tablas básicas"""
    if not supabase_service:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        results = supabase_service.create_basic_tables()
        return jsonify({
            "success": True,
            "message": "Tablas creadas/verificadas",
            "results": results,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Error en api_create_tables: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@techview_bp.route('/api/fix-table', methods=['POST'])
def api_fix_table():
    """API: Reparar tabla finances (agregar columnas)"""
    if not supabase_service:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        results = supabase_service.add_missing_columns()
        return jsonify({
            "success": True,
            "message": f"Se agregaron {len(results['added_columns'])} columnas",
            "results": results,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Error en api_fix_table: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@techview_bp.route('/api/test-save', methods=['POST'])
def api_test_save():
    """API: Probar operación de guardado"""
    if not supabase_service:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        results = supabase_service.test_save_operation()
        return jsonify(results)
    except Exception as e:
        logger.error(f"❌ Error en api_test_save: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@techview_bp.route('/api/device/<path:device_id>')
def api_get_device(device_id):
    """API: Obtener información de dispositivo"""
    if not supabase_service:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        logger.info(f"📡 API GET device: {device_id}")
        data = supabase_service.get_device_detail(device_id)
        return jsonify(data)
    except Exception as e:
        logger.error(f"❌ Error en api_get_device: {e}")
        return jsonify({
            "error": str(e),
            "device_id": device_id,
            "timestamp": datetime.now().isoformat()
        }), 500

@techview_bp.route('/api/save', methods=['POST'])
def api_save_data():
    """API: Guardar datos financieros - ENDPOINT PRINCIPAL"""
    try:
        logger.info("=== INICIO api_save_data ===")
        
        if not supabase_service:
            return jsonify({"error": "Servicio no disponible"}), 503
        
        # Obtener datos
        if request.content_type == 'application/json':
            data = request.get_json()
        else:
            # Intentar parsear como JSON
            raw_data = request.get_data(as_text=True)
            logger.debug(f"Raw data recibido: {raw_data[:200]}...")
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON inválido: {e}")
                return jsonify({
                    "error": f"JSON inválido: {str(e)}",
                    "raw_data_sample": raw_data[:100]
                }), 400
        
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400
        
        logger.info(f"📤 Datos recibidos: {list(data.keys())}")
        logger.info(f"📤 Device ID: {data.get('device_id', 'NO PROVIDED')}")
        
        # Guardar
        success, message = supabase_service.save_device_financials(data)
        
        logger.info(f"💾 Resultado guardado: success={success}, message={message}")
        logger.info("=== FIN api_save_data ===")
        
        if success:
            return jsonify({
                "success": True,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "device_id": data.get('device_id')
            })
        else:
            return jsonify({
                "success": False,
                "error": message,
                "timestamp": datetime.now().isoformat(),
                "device_id": data.get('device_id')
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Error crítico en api_save_data: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Error crítico: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

# ============================================
# ENDPOINTS DE COMPATIBILIDAD
# ============================================

@techview_bp.route('/api/metrics/buffer', methods=['POST'])
def api_buffer_metric():
    """API: Bufferizar métrica (para monitor_service)"""
    if not supabase_service:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        data = request.get_json()
        metric_type = data.get('type')
        value = data.get('value')
        device_id = data.get('device_id')
        tags = data.get('tags')
        
        success = supabase_service.buffer_metric(metric_type, value, device_id, tags)
        
        return jsonify({
            "success": success,
            "message": "Métrica bufferizada" if success else "Error bufferizando métrica"
        })
    except Exception as e:
        logger.error(f"❌ Error en api_buffer_metric: {e}")
        return jsonify({"error": str(e)}), 500

@techview_bp.route('/api/device/status', methods=['POST'])
def api_update_device_status():
    """API: Actualizar estado de dispositivo (para monitor_service)"""
    if not supabase_service:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        status = data.get('status')
        location = data.get('location')
        
        success = supabase_service.upsert_device_status(device_id, status, location)
        
        return jsonify({
            "success": success,
            "message": "Estado actualizado" if success else "Error actualizando estado"
        })
    except Exception as e:
        logger.error(f"❌ Error en api_update_device_status: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
# INICIALIZACIÓN
# ============================================

def initialize_techview():
    """Función para inicializar el módulo TechView"""
    logger.info("🚀 Inicializando módulo TechView...")
    
    if supabase_service:
        logger.info("✅ TechView listo para usar")
        
        # Verificar tablas al iniciar (solo en desarrollo)
        if os.environ.get('FLASK_ENV') == 'development':
            try:
                logger.info("🔍 Verificando tablas en desarrollo...")
                results = supabase_service.check_database_tables()
                logger.info(f"📊 Tablas verificadas: {len(results.get('tables', {}))}")
            except Exception as e:
                logger.warning(f"⚠️  No se pudieron verificar tablas: {e}")
    else:
        logger.error("❌ TechView NO inicializado - SupabaseService falló")

# Inicializar al importar
initialize_techview()

# ============================================
# EJECUCIÓN DIRECTA (SOLO PARA PRUEBAS)
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 MÓDULO TECHVIEW - MODO PRUEBA")
    print("=" * 60)
    
    if supabase_service:
        print("✅ SupabaseService inicializado correctamente")
        
        # Ejecutar diagnóstico
        print("\n🔍 Ejecutando diagnóstico...")
        try:
            results = supabase_service.check_database_tables()
            for table, info in results.get('tables', {}).items():
                print(f"  {table}: {info.get('status')} ({info.get('count')} registros)")
        except Exception as e:
            print(f"❌ Error en diagnóstico: {e}")
    else:
        print("❌ ERROR: No se pudo inicializar SupabaseService")
        print("💡 Verifica las variables de entorno:")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_KEY")
    
    print("\n" + "=" * 60)
