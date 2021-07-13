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
    def __init__(self, bus, address, species):
        self.address = address
        self.bus = bus
        self.species = species
        self.moisture = None
        self.brightness = None
        self.last_measurement = 0
        peripherals = self.bus.scan()
        if address not in peripherals:
            raise ValueError("The given address cannot be found on the bus")
            exit(1)

    def get_measurements(self):
        buf = bytearray(8)
        self.timestamp = datetime.datetime.now()
        self.bus.readfrom_into(self.address, buf, start=0, end=8)
        self.moisture = struct.unpack('f', buf[0:4])[0]
        self.moisture = 255 - self.moisture
        self.brightness = struct.unpack('f', buf[4:8])[0]
        self.brightness = 255 - self.brightness
        if self.moisture > 255 and self.moisture < 0:
            raise ValueError("Moisture level for Pot {} outside of allowed range".format(self.address))
        if self.brightness > 255 and self.brightness < 0:
            raise ValueError("Brightness level for Pot {} outside of allowed range".format(self.address))


