import time
import board
import busio
import adafruit_bme280
i2c = busio.I2C(board.SCL, board.SDA)
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)
while True:
    print("\nTemperature: {:.1f} C".format(bme280.temperature))
    print("Humidity: {:.1f} %%".format(bme280.humidity))
    print("Pressure: {:.1f} hPa".format(bme280.pressure))
    time.sleep(2)
