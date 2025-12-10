import os
import asyncio
import json
import logging
from datetime import datetime
from typing import Set
from aiohttp import web, WSMsgType
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv
from sensors import DHT22, BMP280, GY32, Sensor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "")
DHT_PIN = os.getenv("DHT_PIN", "GPIO4")

# Debug: Print configuration
logger.info("=" * 50)
logger.info("INFLUXDB CONFIGURATION:")
logger.info(f"INFLUX_URL: {INFLUX_URL}")
logger.info(f"INFLUX_TOKEN: {INFLUX_TOKEN}")
logger.info(f"INFLUX_ORG: {INFLUX_ORG}")
logger.info(f"INFLUX_BUCKET: {INFLUX_BUCKET}")
logger.info("=" * 50)

# WebSocket clients
ws_clients: Set[web.WebSocketResponse] = set()

# InfluxDB client
influx_client = None
write_api = None

def init_influx():
    global influx_client, write_api
    try:
        logger.info("Initializing InfluxDB client...")
        influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        
        # Test the connection
        health = influx_client.health()
        logger.info(f"✓ InfluxDB client initialized successfully - Status: {health.status}")
    except Exception as e:
        logger.error(f"✗ InfluxDB initialization failed: {e}")

def write_to_influx(data):
    if write_api is None:
        logger.warning("write_api is None, skipping write")
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
        
        logger.debug(f"Writing point: measurement=sensor_data, tag=sensor:{data.sensor_type}, fields={data.fields}, time={timestamp}")
        
        # Write with explicit bucket and org
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        
        logger.info(f"✓ Written to InfluxDB: {data.sensor_type} - {data.fields}")
    except Exception as e:
        logger.error(f"✗ InfluxDB write error: {e}", exc_info=True)

async def broadcast_to_clients(data):
    if not ws_clients:
        return
    
    # Create message once for all clients
    message_dict = {
        "sensor_type": data.sensor_type,
        "fields": {k.lower(): v for k, v in data.fields.items()},
        "timestamp": data.timestamp.isoformat()
    }
    message = json.dumps(message_dict)
    
    # Broadcast to all clients concurrently
    tasks = [ws.send_str(message) for ws in ws_clients]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Clean up disconnected clients
    disconnected = {ws for ws, result in zip(ws_clients, results) 
                   if isinstance(result, Exception)}
    
    if disconnected:
        ws_clients.difference_update(disconnected)
        logger.info(f"Removed {len(disconnected)} disconnected client(s)")

async def read_all_sensors(sensors):
    while True:
        # Read all sensors concurrently
        tasks = [asyncio.to_thread(sensor.read) for sensor in sensors]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for sensor, result in zip(sensors, results):
            if isinstance(result, Exception):
                logger.error(f"Error reading {sensor.name()}: {result}")
            elif result:
                logger.info(f"{sensor.name()}: {result.fields}")
                write_to_influx(result)
                await broadcast_to_clients(result)
        
        # Wait before reading all sensors again
        await asyncio.sleep(2)


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    ws_clients.add(ws)
    logger.info(f"Client connected. Total clients: {len(ws_clients)}")
    
    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                logger.error(f'WebSocket connection closed with exception {ws.exception()}')
    finally:
        ws_clients.discard(ws)
        logger.info(f"Client disconnected. Total clients: {len(ws_clients)}")
    
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
        logger.info(f"✓ DHT22 initialized on {DHT_PIN}")
    except Exception as e:
        logger.error(f"✗ DHT22 initialization failed: {e}")
    
    try:
        sensors.append(BMP280(address=0x76))
        logger.info("✓ BMP280 initialized")
    except Exception as e:
        logger.error(f"✗ BMP280 initialization failed: {e}")
    
    try:
        sensors.append(GY32(address=0x23))
        logger.info("✓ GY32 initialized")
    except Exception as e:
        logger.error(f"✗ GY32 initialization failed: {e}")
    
    if not sensors:
        logger.warning("No sensors initialized!")
    
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