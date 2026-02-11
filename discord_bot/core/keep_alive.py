from aiohttp import web
import asyncio

async def handle(request):
    return web.Response(text="🤖 SyncOps está vivo y operando.")

async def start_server():
    app = web.Application()
    app.add_routes([web.get('/', handle), web.get('/health', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    # Render asigna un puerto dinámico en la variable PORT, o usa 8080 por defecto
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🌍 Servidor Web Keep-Alive iniciado en puerto 8080")

def keep_alive():
    """Función para llamar desde el main loop"""
    loop = asyncio.get_event_loop()
    loop.create_task(start_server())