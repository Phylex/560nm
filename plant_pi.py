import time
import struct
import board
import busio

i2c = busio.I2C(board.SCL, board.SDA, 100000)

plants = i2c.scan()
if !i2c.try_lock():
    print("Could not aquire exclusive use of the i2c")
    exit(1)

while True:
    for plant in plants:
        buf = bytearray(8)
        print("Reading from plant {}".format(plant))
        i2c.readfrom_into(plant, buf, 0, 8)
        raw_moist = buf[:4]
        raw_bright = buf[4:]
        moisture = struct.unpack('f', raw_moist)
        brightness = struct.unpack('f', raw_bright)
        print("Moisture: {}".format(moisture))
        print("Brightness: {}".format(brightness))
        sleep(1)
              