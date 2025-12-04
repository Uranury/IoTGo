import adafruit_dht
import board
import time

dht = adafruit_dht.DHT22(board.D4)  # GPIO4

while True:
    try:
        temp = dht.temperature
        hum = dht.humidity
        print(f"Temp: {temp}°C, Humidity: {hum}%")
    except RuntimeError as e:
        print(f"Read error (maybe disconnected): {e}")
    time.sleep(2)
