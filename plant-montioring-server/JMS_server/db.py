""" Module containing all the needed database commands used by the
JMS-Server """
from datetime import datetime as dt
import aiopg.sa
from sqlalchemy import (
        MetaData, Table, Column, ForeignKey,
        Integer, Float, String, DateTime,
        text
)
from sqlalchemy.sql import (select, desc)

meta = MetaData()

plant = Table(
        'plant',
        meta,
        Column('address', Integer, primary_key=True),
        Column('species', String(200), nullable=False),
)

measurement = Table(
        'measurement',
        meta,
        Column('id', Integer, primary_key=True),
        Column('timestamp', DateTime, nullable=False),
        Column('moisture', Float, nullable=False),
        Column('brightness', Float, nullable=False),
        Column('plant_address',
            ForeignKey('plant.address', ondelete='CASCADE')),
)


async def init_pg(app):
    config = app['config']['postgres']
    engine = await aiopg.sa.create_engine(
            database=config['database'],
            user=config['user'],
            password=config['password'],
            host=config['host'],
            port=config['port'],
            minsize=config['minsize'],
            maxsize=config['maxsize']
    )
    app['db'] = engine


async def close_pg(app):
    app['db'].close()
    await app['db'].wait_closed()


async def get_plants(conn):
    stmt = plant.select().order_by(plant.c.address)
    records = await conn.execute(stmt)
    return await records.fetchall()

async def add_plant(conn, species, address):
    stmt = plant.insert().values(species=species, address=address)
    await conn.execute(stmt)

async def add_measurement(conn, plant_address, brightness, moisture, timestamp):
    stmt = measurement.insert().values(
            plant_address=plant_address,
            brightness=brightness,
            moisture=moisture,
            timestamp=timestamp
    )
    await conn.execute(stmt)

async def get_measurements(conn, start_time, stop_time, plant_id):
    stmt = measurement.select().where(
            measurement.c.timestamp >= start_time).where(
                    measurement.c.timestamp <= stop_time).where(
                            measurement.c.plant_id == plant_id).order_by(
                                    measurement.c.timestamp)
    result = await conn.execute(stmt)
    return await result.fetchall()

async def get_last_measurement(conn):
    stmt = measurement.select(measurement.c.timestamp).order_by(
            desc(measurement.c.timestamp))
    result = await conn.execute(stmt)
    return await result.first()
