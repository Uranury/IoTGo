import os
import asyncio
import json
from datetime import datetime
from typing import Set
from aiohttp import web, WSMsgType
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv
from sensors import DHT22, BMP280, GY32, Sensor

# Load environment variables
load_dotenv()

# Configuration
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "")
DHT_PIN = os.getenv("DHT_PIN", "GPIO4")

# Debug: Print configuration
print("=" * 50)
print("INFLUXDB CONFIGURATION:")
print(f"INFLUX_URL: {INFLUX_URL}")
print(f"INFLUX_TOKEN: {INFLUX_TOKEN}")
print(f"INFLUX_ORG: {INFLUX_ORG}")
print(f"INFLUX_BUCKET: {INFLUX_BUCKET}")
print("=" * 50)

# WebSocket clients
ws_clients: Set[web.WebSocketResponse] = set()

# InfluxDB client
influx_client = None
write_api = None

def init_influx():
    global influx_client, write_api
    try:
        print("Initializing InfluxDB client...")
        influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        
        # Test the connection
        health = influx_client.health()
        print(f"✓ InfluxDB client initialized successfully - Status: {health.status}")
    except Exception as e:
        print(f"✗ InfluxDB initialization failed: {e}")

def write_to_influx(data):
    if write_api is None:
        print("WARNING: write_api is None, skipping write")
        return
    
    try:
        # Use current time in UTC
        from datetime import timezone
        timestamp = datetime.now(timezone.utc)
        
        point = Point("sensor_data") \
            .tag("sensor", data.sensor_type) \
            .time(timestamp)
        
        for key, value in data.fields.items():
            point = point.field(key, float(value))
        
        # Debug: print the point before writing
        print(f"DEBUG: Writing point: measurement=sensor_data, tag=sensor:{data.sensor_type}, fields={data.fields}, time={timestamp}")
        
        # Write with explicit bucket and org
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        
        print(f"✓ Written to InfluxDB: {data.sensor_type} - {data.fields}")
    except Exception as e:
        import traceback
        print(f"✗ InfluxDB write error: {e}")
        print(f"✗ Full traceback:")
        traceback.print_exc()

async def broadcast_to_clients(data):
    if not ws_clients:
        return
    
    message_dict = {
        "sensor_type": data.sensor_type,
        "fields": {k.lower(): v for k, v in data.fields.items()},
        "timestamp": data.timestamp.isoformat()
    }
    
    message = json.dumps(message_dict)
    disconnected = set()
    
    for ws in ws_clients:
        try:
            await ws.send_str(message)
        except Exception as e:
            print(f"WebSocket send error: {e}")
            disconnected.add(ws)
    
    # Remove disconnected clients
    for ws in disconnected:
        ws_clients.discard(ws)

async def read_all_sensors(sensors):
    while True:
        for sensor in sensors:
            try:
                data = sensor.read()
                if data:
                    print(f"{sensor.name()}: {data.fields}")
                    write_to_influx(data)
                    await broadcast_to_clients(data)
            except Exception as e:
                print(f"Error reading {sensor.name()}: {e}")
        
        # Wait before reading all sensors again
        await asyncio.sleep(2)


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    ws_clients.add(ws)
    print(f"Client connected. Total clients: {len(ws_clients)}")
    
    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                print(f'WebSocket connection closed with exception {ws.exception()}')
    finally:
        ws_clients.discard(ws)
        print(f"Client disconnected. Total clients: {len(ws_clients)}")
    
    return ws

async def index_handler(request):
    return web.FileResponse('./static/index.html')

async def start_background_tasks(app):
    sensors = app['sensors']
    app['sensor_task'] = asyncio.create_task(read_all_sensors(sensors))

async def init_app():
    app = web.Application()
    
    # Setup routes
    app.router.add_get('/', index_handler)
    app.router.add_get('/ws', websocket_handler)
    app.router.add_static('/static', './static')
    
    # Initialize sensors
    sensors = []
    try:
        sensors.append(DHT22(DHT_PIN))
        print(f"✓ DHT22 initialized on {DHT_PIN}")
    except Exception as e:
        print(f"✗ DHT22 initialization failed: {e}")
    
    try:
        sensors.append(BMP280(address=0x76))
        print("✓ BMP280 initialized")
    except Exception as e:
        print(f"✗ BMP280 initialization failed: {e}")
    
    try:
        sensors.append(GY32(address=0x23))
        print("✓ GY32 initialized")
    except Exception as e:
        print(f"✗ GY32 initialization failed: {e}")
    
    if not sensors:
        print("WARNING: No sensors initialized!")
    
    # Save sensors to app for background task
    app['sensors'] = sensors
    
    # Initialize InfluxDB
    init_influx()
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup)
    
    return app


async def cleanup(app):
    # Cancel sensor reading task
    if 'sensor_task' in app:
        app['sensor_task'].cancel()
        try:
            await app['sensor_task']
        except asyncio.CancelledError:
            pass
    
    # Close sensors
    for sensor in app.get('sensors', []):
        sensor.close()
    
    # Close InfluxDB client
    if influx_client:
        influx_client.close()

if __name__ == '__main__':
    web.run_app(init_app(), host='0.0.0.0', port=8080)