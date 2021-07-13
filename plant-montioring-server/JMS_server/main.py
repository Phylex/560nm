# examples/server_simple.py
from aiohttp import web
import asyncio as aio
import datetime
from MockPlantManager import PlantManager
import db
import aiohttp_jinja2
import jinja2
from views import index
from settings import config, BASE_DIR
from routes import setup_routes


async def measure_plants(app: web.Application) -> None:
    """ measure the plants periodically """
    pm = app["Plant-Manager"]
    config = app['config']
    async with app['db'].acquire() as conn:
        last_measurement = await db.get_last_measurement(conn)
        while True:
            try:
                now = datetime.datetime.now()
                if now - last_measurement > config['measurement-interval']:
                    measurement = pm.measure_plants()
                    await db.add_measurement(conn, now, measurement)
                    last_measurement = now
                else:
                    await aio.sleep(1)
            except aio.CancelledError:
                break


async def handle(request):
    name = request.match_info.get('name', "Anonymous")
    text = "Hello, " + name
    return web.Response(text=text)


async def start_measurement(app: web.Application) -> None:
    """ Function that starts up the measurement task and the
    plant management task"""
    app["PlantManager"] = PlantManager(app)
    # app["measurement-task"] = aio.create_task(measure_plants(app))


async def cleanup_background_task(app: web.Application) -> None:
    """ Function that stops and cleans up the measurement and management
    task"""
    print("cleanup background tasks ...")
    # app["measurement-task"].cancel()
    # await app["measurement-task"]


def init() -> web.Application:
    app = web.Application()
    app["config"] = config
    aiohttp_jinja2.setup(app,
            loader=jinja2.FileSystemLoader(str(BASE_DIR / 'JMS_server' / 'templates')))
    setup_routes(app)
    app.on_startup.append(db.init_pg)
    app.on_startup.append(start_measurement)
    app.on_cleanup.append(cleanup_background_task)
    # app.on_shutdown.append(on_shutdown)
    app.on_cleanup.append(db.close_pg)
    return app

# run the app
web.run_app(init())
