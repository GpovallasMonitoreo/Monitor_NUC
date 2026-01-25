import os
from supabase import create_client

def diagnose_database():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    print("🔍 Diagnóstico de Base de Datos Supabase")
    print(f"URL: {url}")
    print(f"KEY: {key[:20]}...")
    
    try:
        client = create_client(url, key)
        
        # 1. Verificar si la tabla 'finances' existe
        print("\n1. Verificando tabla 'finances'...")
        try:
            result = client.table("finances").select("count", count="exact").limit(1).execute()
            print(f"   ✅ Tabla 'finances' existe: {result.count} registros")
        except Exception as e:
            print(f"   ❌ Error accediendo a 'finances': {e}")
            
        # 2. Verificar si la tabla 'devices' existe
        print("\n2. Verificando tabla 'devices'...")
        try:
            result = client.table("devices").select("count", count="exact").limit(1).execute()
            print(f"   ✅ Tabla 'devices' existe: {result.count} registros")
        except Exception as e:
            print(f"   ❌ Error accediendo a 'devices': {e}")
            
        # 3. Verificar columnas de 'finances'
        print("\n3. Verificando estructura de 'finances'...")
        try:
            # Obtener una fila para ver las columnas
            result = client.table("finances").select("*").limit(1).execute()
            if result.data:
                print(f"   ✅ Columnas encontradas: {list(result.data[0].keys())}")
            else:
                print("   ℹ️  Tabla 'finances' vacía")
        except Exception as e:
            print(f"   ❌ Error obteniendo estructura: {e}")
            
        # 4. Buscar el device_id problemático
        print("\n4. Buscando device_id problemático...")
        device_id = "MX_CM_EV_MGP_01_3591\tCalle Arquímedes 173 :238"
        print(f"   Device ID crudo: {repr(device_id)}")
        print(f"   Device ID URL encoded: {device_id.replace(chr(9), '%09')}")
        
        # Buscar en devices
        try:
            result = client.table("devices").select("*").eq("device_id", device_id).execute()
            if result.data:
                print(f"   ✅ Device encontrado en tabla 'devices': {result.data[0]}")
            else:
                print(f"   ⚠️  Device NO encontrado en tabla 'devices'")
        except Exception as e:
            print(f"   ❌ Error buscando device: {e}")
            
        # Buscar en finances
        try:
            result = client.table("finances").select("*").eq("device_id", device_id).execute()
            if result.data:
                print(f"   ✅ Device encontrado en tabla 'finances': ID={result.data[0].get('id')}")
            else:
                print(f"   ⚠️  Device NO encontrado en tabla 'finances'")
        except Exception as e:
            print(f"   ❌ Error buscando en finances: {e}")
            
        # 5. Verificar restricción UNIQUE
        print("\n5. Probando inserción de test...")
        test_data = {
            "device_id": "TEST_DEVICE_123",
            "capex_screen": 1000,
            "revenue_monthly": 500
        }
        try:
            result = client.table("finances").upsert(test_data, on_conflict="device_id").execute()
            print(f"   ✅ Test de inserción exitoso")
            
            # Limpiar test
            client.table("finances").delete().eq("device_id", "TEST_DEVICE_123").execute()
        except Exception as e:
            print(f"   ❌ Error en test de inserción: {e}")
            
    except Exception as e:
        print(f"❌ Error general de conexión: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose_database()
