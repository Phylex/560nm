import time
import struct
import board
import busio
from prometheus_client import start_http_server, Gauge

i2c = busio.I2C(board.SCL, board.SDA)

class PlantPot():
    def __init__(bus, address):
        self.address = address
        self.bus = bus
        self.moisture = None
        self.brightness = None
        self.last_measurement = None
        self.m = Gauge('plant_{}_moisture'.format(self.address),
                       'The moisture level in pot of plant {}'.format(self.address))
        self.m.set_function(lambda: self.get_moisture())
        self.b = Gauge('plant_{}_brightness'.format(self.address),
                       'The local brightness of the environment at Plant {}'.format(self.address))
        self.b.set_function(lambda: self.get_brightness())
        peripherals = bus.scan()
        if address is not in peripherals:
            raise ValueError("The given address cannot be found on the bus")
            exit(1)

    def get_measurements(self):
        buf = bytearray(8)
        self.last_measurement = time.time()
        self.bus.readfrom_into(self.address, buf, 0, 8)
        self.moisture = struct.unpack('f', buf[0:4])
        self.moisture = 255 - self.moisture
        self.brightness = struct.unpack('f', buf[4:8])
        self.brightness = 255 - self.brightness
        if self.moisture > 255 and self.moisture < 0:
            raise ValueError("Moisture level for Pot {} outside of allowed range".format(self.address))
        if self.brightness > 255 and self.brightness < 0:
            raise ValueError("Brightness level for Pot {} outside of allowed range".format(self.address))

    def get_brightness(self):
        now = time.time()
        if abs(now - self.last_measurement) > 1:
            self.get_measurements()
        return self.brightness

    def get_moisture(self):
        now = time.time()
        if abs(now - self.last_measurement) > 1:
            self.get_measurements()
        return self.moisture


peripherals = i2c.scan()
if !i2c.try_lock():
    print("Could not aquire exclusive use of the i2c")
    exit(1)

plants = []
for p in peripherals:
    pot = PlantPot(i2c, p)
    plants.append(pot)

start_http_server(8000)
