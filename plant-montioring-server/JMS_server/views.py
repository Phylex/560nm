from aiohttp import web
import aiohttp_jinja2
from datetime import datetime as dt
import db

@aiohttp_jinja2.template('index.html')
async def index(request):
    plants = await request.app['PlantManager'].get_plants()
    unregistered_plants = await request.app['PlantManager'].get_unregistered_plants()
    return {'plants': plants, 'unregistered_plants': unregistered_plants}


async def get_data(request):
    async with request.app['db'].acquire() as conn:
        start_time = dt(2000, 1, 1, 0, 0, 0)
        end_time = dt(2022, 1, 1, 0, 0, 0)
        data = await db.get_measurements(conn, start_time, end_time, 0)
        data = [dict(d) for d in data]
        return web.Response(text=str(data))

