from aiohttp import web
import asyncio
import threading
import time

async def handle(request):
    return web.Response(text="🤖 SyncOps está vivo y operando.")

async def handle_health(request):
    return web.Response(text="✅ OK", status=200)

async def start_server():
    app = web.Application()
    app.add_routes([
        web.get('/', handle),
        web.get('/health', handle_health),
        web.get('/ping', handle)
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    # Render asigna un puerto dinámico en la variable PORT, o usa 8080 por defecto
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 Servidor Web Keep-Alive iniciado en puerto {port}")
    
    # Mantener el servidor corriendo
    while True:
        await asyncio.sleep(3600)

def run_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_server())

def keep_alive():
    """Función para llamar desde el main loop"""
    import os
    print("🚀 Iniciando servidor keep-alive...")
    # Iniciar en un hilo separado
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    print("✅ Servidor keep-alive iniciado en segundo plano")
