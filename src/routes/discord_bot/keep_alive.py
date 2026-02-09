from aiohttp import web
import asyncio
import threading
import os
import sys

async def handle(request):
    return web.Response(text="🤖 SyncOps Discord Bot está vivo y operando.")

async def handle_health(request):
    return web.Response(text="✅ OK - Discord Bot", status=200)

async def start_server():
    app = web.Application()
    app.add_routes([
        web.get('/', handle),
        web.get('/health', handle_health),
        web.get('/ping', handle)
    ])
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Usar puerto dinámico de Render
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    print(f"🌍 Servidor Web Keep-Alive iniciado en puerto {port}")
    await site.start()
    
    # Mantener el servidor corriendo
    while True:
        await asyncio.sleep(3600)

def run_server():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_server())
    except Exception as e:
        print(f"❌ Error en servidor keep-alive: {e}")

def keep_alive():
    """Iniciar servidor web en segundo plano para mantener el bot activo"""
    print("🚀 Iniciando servidor keep-alive para Render...")
    
    # Verificar si estamos en Render
    if os.environ.get('RENDER') or os.environ.get('PORT'):
        t = threading.Thread(target=run_server, daemon=True)
        t.start()
        print("✅ Servidor keep-alive iniciado en segundo plano")
    else:
        print("ℹ️  No en entorno Render, servidor keep-alive omitido")
