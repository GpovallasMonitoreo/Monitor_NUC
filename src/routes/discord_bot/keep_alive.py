"""
Servidor web simple para mantener el bot activo en Render
"""

from aiohttp import web
import asyncio
import threading
import os
import sys

async def handle_root(request):
    """Manejar solicitud a la raíz"""
    return web.Response(
        text="🤖 SyncOps Discord Bot está activo y funcionando\n",
        headers={'Content-Type': 'text/plain; charset=utf-8'}
    )

async def handle_health(request):
    """Endpoint de health check para Render"""
    return web.Response(
        text="✅ OK - SyncOps Bot\n",
        status=200,
        headers={'Content-Type': 'text/plain; charset=utf-8'}
    )

async def handle_ping(request):
    """Endpoint de ping"""
    return web.Response(
        text="🏓 Pong!\n",
        headers={'Content-Type': 'text/plain; charset=utf-8'}
    )

async def handle_info(request):
    """Endpoint de información"""
    import platform
    info = f"""
🤖 SyncOps Discord Bot
=====================
Estado: Activo
Python: {platform.python_version()}
Platform: {platform.platform()}
Director: {os.getcwd()}
Entorno: {'Render' if os.getenv('RENDER') else 'Local'}
Puerto: {os.getenv('PORT', 'No definido')}
=====================
Endpoints:
  /         - Esta página
  /health   - Health check
  /ping     - Ping
  /info     - Información del sistema
"""
    return web.Response(
        text=info,
        headers={'Content-Type': 'text/plain; charset=utf-8'}
    )

async def start_server():
    """Iniciar servidor web"""
    app = web.Application()
    
    # Configurar rutas
    app.add_routes([
        web.get('/', handle_root),
        web.get('/health', handle_health),
        web.get('/ping', handle_ping),
        web.get('/info', handle_info),
    ])
    
    # Configurar CORS (opcional)
    # cors = aiohttp_cors.setup(app, defaults={
    #     "*": aiohttp_cors.ResourceOptions(
    #         allow_credentials=True,
    #         expose_headers="*",
    #         allow_headers="*",
    #     )
    # })
    
    # for route in list(app.router.routes()):
    #     cors.add(route)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Obtener puerto de Render o usar 8080
    port = int(os.environ.get("PORT", 8080))
    
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"🌍 Servidor web iniciado en http://0.0.0.0:{port}")
    print(f"🔗 Health check: http://0.0.0.0:{port}/health")
    
    # Mantener el servidor corriendo
    while True:
        await asyncio.sleep(3600)  # Dormir 1 hora

def run_server():
    """Ejecutar servidor en un hilo separado"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_server())
    except Exception as e:
        print(f"❌ Error en servidor web: {e}")

def keep_alive():
    """Iniciar servidor web en segundo plano para mantener activo el bot"""
    print("🚀 Iniciando servidor keep-alive...")
    
    # Solo iniciar en Render
    if os.environ.get('RENDER') or os.environ.get('PORT'):
        t = threading.Thread(target=run_server, daemon=True)
        t.start()
        print("✅ Servidor keep-alive iniciado en segundo plano")
    else:
        print("ℹ️  Entorno local detectado, keep-alive omitido")
