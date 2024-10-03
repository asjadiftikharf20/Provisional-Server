import asyncio
import uvloop
import logging
import json
import aiohttp
import time
from aiohttp import web
from azure.iot.hub import IoTHubRegistryManager
from azure.iot.hub import sastoken
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# IoT Hub connection string (replace with your actual connection string)
IOTHUB_CONNECTION_STRING = "HostName=iothubdevuae.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=TgNmv49DIduLOsnHU7ccaESSOcXnpKu9UAIoTOMlm0s="

# IoT Hub URL for sending telemetry
IOT_HUB_URL = "https://iothubdevuae.azure-devices.net/devices/{device_id}/messages/events?api-version=2020-09-30"

# SAS token time limit (e.g., 1 hour)
SAS_TOKEN_TIME_LIMIT = 3600

# Redis connection (will be initialized in the start_server function)
redis_client = None
session = None  # Global aiohttp session

async def create_sas_token(device_id, primary_key, expiry):
    """Create a new SAS token for the device."""
    resource_uri = f"{IOTHUB_CONNECTION_STRING.split(';')[0].split('=')[1]}/devices/{device_id}"
    sas_token = sastoken.SasToken(resource_uri, primary_key, ttl=expiry)
    logging.info(f"Generated SAS token for {device_id}: {sas_token}")
    return str(sas_token)

async def register_device_on_iot_hub(client_id):
    """Register a device on IoT Hub or fetch its existing credentials."""
    global redis_client
    start_time = time.time()  # Start timing device registration
    # Check if the device is already registered in Redis
    device_info = await redis_client.hgetall(client_id)

    if device_info:
        logging.info(f"Device {client_id} already registered.")
        return device_info.get('primary_key'), device_info.get('secondary_key'), device_info.get('sas_token')

    registry_manager = IoTHubRegistryManager(IOTHUB_CONNECTION_STRING)

    try:
        device_info = registry_manager.get_device(client_id)
        primary_key = device_info.authentication.symmetric_key.primary_key
        secondary_key = device_info.authentication.symmetric_key.secondary_key
        logging.info(f"Device {client_id} already registered on IoT Hub.")
    except Exception as e:
        logging.info(f"Device {client_id} not found on IoT Hub. Registering new device. Error: {e}")
        try:
            device = registry_manager.create_device_with_sas(client_id, None, None, None)
            primary_key = device.authentication.symmetric_key.primary_key
            secondary_key = device.authentication.symmetric_key.secondary_key
            logging.info(f"Device {client_id} registered successfully on IoT Hub.")
        except Exception as e:
            logging.error(f"Failed to register device {client_id}: {e}")
            return None, None, None

    # Create a new SAS token for the device
    expiry = int(time.time()) + SAS_TOKEN_TIME_LIMIT
    sas_token = await create_sas_token(client_id, primary_key, expiry)

    # Store the device credentials in Redis
    await redis_client.hset(client_id, mapping={
        'primary_key': primary_key,
        'secondary_key': secondary_key,
        'sas_token': sas_token,
        'token_expiry': str(time.time() + SAS_TOKEN_TIME_LIMIT)
    })

    # Set expiry in Redis for the stored data
    await redis_client.expire(client_id, SAS_TOKEN_TIME_LIMIT)

    end_time = time.time()  # End timing device registration
    logging.info(f"Device registration completed in {(end_time - start_time) * 1000:.2f} ms")

    return primary_key, secondary_key, sas_token

async def send_telemetry_to_iot_hub(device_id, message):
    """Send telemetry data to IoT Hub."""
    try:
        start_time = time.time()  # Start timing telemetry sending
        device_info = await redis_client.hgetall(device_id)
        if not device_info:
            logging.error(f"Device {device_id} not registered.")
            return

        # Check if SAS token has expired
        if time.time() > float(device_info['token_expiry']):
            logging.info(f"SAS token for device {device_id} expired. Generating new token.")
            expiry = 86400  # 24 hours
            sas_token = await create_sas_token(device_id, device_info['primary_key'], expiry)
            await redis_client.hset(device_id, 'sas_token', sas_token)
            await redis_client.hset(device_id, 'token_expiry', str(time.time() + expiry))

        url = IOT_HUB_URL.format(device_id=device_id)
        headers = {
            "Authorization": device_info['sas_token'],
            "Content-Type": "application/json"
        }

        telemetry_data = json.dumps({
            'device_id': device_id,
            'message': message
        })

        # Use an asynchronous context manager for the session post
        async with session.post(url, headers=headers, data=telemetry_data) as response:
            if response.status == 204:
                logging.info(f"Telemetry sent for device {device_id}")
            else:
                logging.error(f"Failed to send telemetry. Status: {response.status}, Response: {await response.text()}")

        end_time = time.time()  # End timing telemetry sending
        logging.info(f"Telemetry sending completed in {(end_time - start_time) * 1000:.2f} ms")

    except Exception as e:
        logging.error(f"Error sending telemetry for device {device_id}: {e}")

async def handle_post_request(request):
    """Handle incoming POST requests, validate JSON, and send telemetry."""
    start_time = time.time()  # Start timing the request
    try:
        data = await request.json()

        if 'device_id' not in data or 'time' not in data:
            return web.json_response({'error': 'Invalid packet. Missing device_id or time.'}, status=400)

        device_id = data['device_id']

        device_info = await register_device_on_iot_hub(device_id)
        if not device_info:
            return web.json_response({'error': 'Failed to register device.'}, status=500)

        await send_telemetry_to_iot_hub(device_id, data)

        latency = (time.time() - start_time) * 1000  # Calculate latency in ms
        logging.info(f"Request handled in {latency:.2f} ms")

        return web.json_response({'status': 'Telemetry received and sent to IoT Hub.'}, status=200)

    except json.JSONDecodeError:
        return web.json_response({'error': 'Invalid JSON format.'}, status=400)

    except Exception as e:
        logging.error(f"Error handling request: {e}")
        return web.json_response({'error': 'Internal Server Error'}, status=500)

async def start_server():
    """Start the aiohttp server and Redis connection."""
    global redis_client, session
    pool = ConnectionPool(host='localhost', port=6379, max_connections=100, decode_responses=True)
    redis_client = redis.Redis(connection_pool=pool)
    session = aiohttp.ClientSession()

    app = web.Application()
    app.router.add_post('/', handle_post_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logging.info("Server started at http://0.0.0.0:8080")

    while True:
        await asyncio.sleep(3600)  # Keep the server running

if __name__ == "__main__":
    # Set the event loop policy to use uvloop for better performance
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    asyncio.run(start_server())
