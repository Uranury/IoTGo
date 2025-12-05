# sensors.py
import time
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional
import adafruit_dht
import board
import busio
import adafruit_bmp280
import adafruit_bh1750

class SensorData:
    def __init__(self, sensor_type: str, fields: Dict[str, float], timestamp: datetime = None):
        self.sensor_type = sensor_type
        self.fields = fields
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self):
        return {
            'sensor_type': self.sensor_type,
            'fields': self.fields,
            'timestamp': self.timestamp.isoformat()
        }

class Sensor(ABC):
    @abstractmethod
    def read(self) -> Optional[SensorData]:
        pass
    
    @abstractmethod
    def name(self) -> str:
        pass
    
    def close(self):
        pass


class DHT22(Sensor):
    def __init__(self, pin_name: str = "GPIO4"):
        pin_map = {
            "GPIO4": board.D4,
            "GPIO17": board.D17,
            "GPIO27": board.D27,
            "GPIO22": board.D22,
        }
        
        pin = pin_map.get(pin_name, board.D4)
        self.dht_device = adafruit_dht.DHT22(pin, use_pulseio=False)
        self.pin_name = pin_name
    
    def name(self) -> str:
        return "DHT22"
    
    def read(self) -> Optional[SensorData]:
        try:
            temperature = self.dht_device.temperature
            humidity = self.dht_device.humidity
            
            if temperature is not None and humidity is not None:
                return SensorData(
                    sensor_type="dht22",
                    fields={
                        "temperature": temperature,
                        "humidity": humidity
                    }
                )
        except RuntimeError as e:
            print(f"DHT22 read error: {e}")
        return None
    
    def close(self):
        self.dht_device.exit()

class BMP280(Sensor):
    def __init__(self, address: int = 0x77):
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=address)
            self.bmp280.sea_level_pressure = 1013.25
        except Exception as e:
            print(f"BMP280 initialization failed: {e}")
            self.bmp280 = None
    
    def name(self) -> str:
        return "BMP280"
    
    def read(self) -> Optional[SensorData]:
        if not self.bmp280:
            return None
        try:
            return SensorData(
                sensor_type="bmp280",
                fields={
                    "temperature": self.bmp280.temperature,
                    "pressure": self.bmp280.pressure,
                    "altitude": self.bmp280.altitude
                }
            )
        except Exception as e:
            print(f"BMP280 read error: {e}")
            return None

class GY32(Sensor):
    def __init__(self, address: int = 0x23):
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.bh1750 = adafruit_bh1750.BH1750(i2c, address=address)
        except Exception as e:
            print(f"GY32 initialization failed: {e}")
            self.bh1750 = None
    
    def name(self) -> str:
        return "GY32"
    
    def read(self) -> Optional[SensorData]:
        if not self.bh1750:
            return None
        try:
            return SensorData(
                sensor_type="gy32",
                fields={
                    "lux": self.bh1750.lux
                }
            )
        except Exception as e:
            print(f"GY32 read error: {e}")
            return None