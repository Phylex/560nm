import numpy as np
import db
import asyncio as aio
from datetime import datetime as dt

class AlreadyRegistered(Exception):
    pass

class PlantManager():
    counter = 0
    cd = 'up'
    def __init__(self, app):
        self.app = app
        self.plants = [0, 1, 2, 3]
        aio.create_task(self.init_from_db())

    async def init_from_db(self):
        async with self.app['db'].acquire() as conn:
            self.registered_plants = [dict(d) for d in await db.get_plants(conn)]

    async def get_plants(self):
        return self.registered_plants

    async def add_plant(self, species, address):
        registered_addresses = [p['address'] for p in self.registered_plants]
        if address in registered_addresses:
            raise AlreadyRegistered
        async with self.app['db'].acquire() as conn:
            await db.add_plant(conn, species, address)
            registered_plants = await db.get_plants(conn)
            self.registered_plants = [dict(d) for d in registered_plants]

    async def get_unregistered_plants(self):
        unregistered_plant_addresses = []
        registered_plant_addresses = [p['address']
                                      for p in self.registered_plants]
        for plant in self.plants:
            if plant not in registered_plant_addresses:
                unregistered_plant_addresses.append(plant)
        return unregistered_plant_addresses

    async def measure_plants(self):
        registered_plant_addresses = [p['address'] for p in self.registered_plants]
        with self.app['db'].acquire() as conn:
            now = dt.now()
            for plant in registered_plant_addresses:
                await db.add_measurement(conn, plant,
                        PlantManager.counter,
                        PlantManager.counter,
                        now
                )
            if PlantManager.counter == 255:
                PlantManager.cd = 'down'
            elif PlantManager.counter == 0:
                PlantManager.cd = 'up'
            elif PlantManager.counter < 255 and PlantManager.cd == 'up':
                PlantManager.counter += 1
            elif PlantManager.counter > 0 and PlantManager.cd == 'down':
                PlantManager.counter -= 1
