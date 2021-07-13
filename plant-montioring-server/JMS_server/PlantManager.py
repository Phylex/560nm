import busio
import board
import db
from PlantPot import PlantPot, adr_range

class PlantBusError(Exception):
    pass

class AlreadyRegistered(Exception):
    pass

class PlantManager():
    async def __init__(self, app):
        self.app = app
        # set up i2c conneciton
        self.i2c = busio.I2C(board.SCL, board.SDA, 100000)
        if self.i2c.try_lock() is False:
            raise PlantBusError
        self.plants = []
        self.unregistered_plants = []
        await self._update_plant_registers()

    async def _update_plant_registers(self):
        peripherals = self.i2c.scan()
        async with self.app['db'].acquire() as conn:
            registered_plants = [dict(p) for p in
                                 await db.get_plants(conn)]
        for p in peripherals:
            if p not in adr_range:
                continue
            if p not in [p['address'] for p in registered_plants]:
                if p not in set(self.unregistered_plants):
                    self.unregistered_plants.append(p)
                continue
            if p not in [pl.address for pl in self.plants]:
                for rp in registered_plants:
                    if p == rp['address']:
                        self.plants.append(PlantPot(self.i2c, p, rp['species']))
                        break

    async def get_plants(self):
        await self._update_plant_registers()
        return self.plants

    async def add_plant(self, species, address):
        registered_addresses = [p.address for p in self.plants]
        if address in registered_addresses:
            raise AlreadyRegistered
        async with self.app['db'].acquire() as conn:
            await db.add_plant(conn, species, address)
            self.plants.append(PlantPot(self.i2c, address, species))


    async def get_unregistered_plants(self):
        await self._update_plant_registers()
        return self.unregistered_plants

    async def measure_plants(self):
        for plant in self.plants:
            plant.get_measurements()
            async with self.app['db'].acqire() as conn:
                await db.add_measurement(conn,
                                         plant.address,
                                         plant.brightness,
                                         plant.moisture,
                                         plant.timestamp)

    async def __del__(self):
        self.i2c.unlock()
