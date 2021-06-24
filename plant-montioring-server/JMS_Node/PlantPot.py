import datetime
import socket
import struct
import sqlite3
import sys
import os
import board
import busio
import asyncio

adr_range = list(range(10, 50))

class PlantPot():
    def __init__(self, bus, address, plant_id):
        self.address = address
        self.bus = bus
        self.id = plant_id
        self.moisture = None
        self.brightness = None
        self.last_measurement = 0
        peripherals = self.bus.scan()
        if address not in peripherals:
            raise ValueError("The given address cannot be found on the bus")
            exit(1)

    def get_measurements(self):
        buf = bytearray(8)
        self.last_measurement = datetime.datetime.now()
        self.bus.readfrom_into(self.address, buf, start=0, end=8)
        self.moisture = struct.unpack('f', buf[0:4])[0]
        self.moisture = 255 - self.moisture
        self.brightness = struct.unpack('f', buf[4:8])[0]
        self.brightness = 255 - self.brightness
        if self.moisture > 255 and self.moisture < 0:
            raise ValueError("Moisture level for Pot {} outside of allowed range".format(self.address))
        if self.brightness > 255 and self.brightness < 0:
            raise ValueError("Brightness level for Pot {} outside of allowed range".format(self.address))


class PlantManager():
    def __init__(self, db_path, min_interval, server_address):
        self.min_interval = min_interval
        # set up socket
        try:
            os.unlink(server_address)
        except OSError:
            if os.path.exists(server_address)
                raise
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(server_address)
        # set up database 
        self.db_path = db_path
        self.db_connection = None
        self.db_cursor = None
        try:
            self.db_connection = sqlite3.connect(self.db_path)
            self.db_cursor = self.db_connection.cursor()
        except sqlite3.Error as e:
            print(f"Error connecting to database {db_path}: {e}")
            sys.exit(1)

        # set up i2c conneciton
        self.i2c = busio.I2C(board.SCL, board.SDA, 100000)
        if self.i2c.try_lock() is False:
            print("Could not reserve Bus, exeting")
            sys.exit(1)
        peripherals = self.i2c.scan()
        self.plants = []
        self.unregistered_plants = []
        for adr in peripherals:
            if adr in adr_range:
                plant_in_db = self.db_cursor.execute(
                        'SELECT id, species '
                        'FROM plant WHERE address = ?',
                        (adr,)).fetchone()
                if plant_in_db is not None:
                    self.plants.append(PlantPot(self.i2c, adr, plant_in_db[0]))
                else:
                    self.unregistered_plants.append(adr)

    async def measure_all_pots(self):
        for plant in self.plants:
            plant.get_measurements()
            self.db_cursor.execute(
                    'INSERT into measurements '
                    '(plant_id, time, moisture, brightness) '
                    'VALUES (?,?,?,?)',
                    (plant.id, plant.last_measurement.timestamp(),
                     plant.moisture, plant.brightness)
            )
        self.db_connection.commit()

    def __del__(self):
        self.db_connection.close()
        self.i2c.unlock()

    def add_all_pots_in_address_range(db_path):
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        i2c = busio.I2C(board.SCL, board.SDA, 100000)
        peripherals = i2c.scan()
        for p in peripherals:
            if p in adr_range:
                plant = cur.execute(
                        'SELECT id, species FROM '
                        'plant WHERE address = ?', (p,)
                ).fetchone()
                if plant is None:
                    species = input(f'Species of plant in pot {p}:')
                    cur.execute(
                            'INSERT into plant '
                            '(address, species) VALUES '
                            '(?, ?)', (p, species))
                    con.commit()
                    print(f'added plant in pot no {p} of the {species} species to the db')

    def setup_database(db_path, schema_path):
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        with open(schema_path) as f:
            cur.executescript(f.read())
            con.commit()
        con.close()
        add_all_pots_in_address_range(db_path)
