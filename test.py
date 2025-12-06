import time
import board
import busio
import adafruit_dht
import adafruit_bmp280

# DHT22 on GPIO4
dht = adafruit_dht.DHT22(board.D4)

# I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# BMP280 at address 0x76
bmp = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x76)

while True:
    # Read DHT22
    try:
        temp = dht.temperature
        hum = dht.humidity
        print(f"DHT22 -> Temp: {temp}°C, Humidity: {hum}%")
    except RuntimeError as e:
        print(f"DHT22 read error: {e}")

    # Read BMP280
    try:
        print(f"BMP280 -> Temp: {bmp.temperature}°C, Pressure: {bmp.pressure} hPa")
    except Exception as e:
        print(f"BMP280 read error: {e}")

    time.sleep(2)
