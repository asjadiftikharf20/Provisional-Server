import asyncio
import logging
import json
import time
import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
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

# Create FastAPI instance
app = FastAPI()

# Redis connection (will be initialized in the start_server function)
redis_client = None
aiohttp_session = None  # Global session for aiohttp

async def create_sas_token(device_id, primary_key, expiry):
    """Create a new SAS token for the device."""
    resource_uri = f"{IOTHUB_CONNECTION_STRING.split(';')[0].split('=')[1]}/devices/{device_id}"
    sas_token = sastoken.SasToken(resource_uri, primary_key, ttl=expiry)
    return str(sas_token)

async def register_device_on_iot_hub(client_id):
    """Register a device on IoT Hub or fetch its existing credentials."""
    global redis_client
    device_info = await redis_client.hgetall(client_id)

    if device_info:
        logging.info(f"Device {client_id} already registered.")
        return (device_info['primary_key'], 
                device_info['secondary_key'], 
                device_info['sas_token'], 
                device_info['token_expiry'])

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
            return None, None, None, None

    expiry = int(time.time()) + SAS_TOKEN_TIME_LIMIT
    sas_token = await create_sas_token(client_id, primary_key, expiry)

    await redis_client.hset(client_id, mapping={
        'primary_key': primary_key,
        'secondary_key': secondary_key,
        'sas_token': sas_token,
        'token_expiry': str(expiry)
    })

    await redis_client.expire(client_id, SAS_TOKEN_TIME_LIMIT)

    return primary_key, secondary_key, sas_token, expiry

async def send_telemetry_to_iot_hub(device_id, message):
    """Send telemetry data to IoT Hub."""
    try:
        device_info = await redis_client.hgetall(device_id)
        if not device_info:
            logging.error(f"Device {device_id} not registered.")
            return

        # Check and refresh SAS token if expired
        if time.time() > float(device_info['token_expiry']):
            logging.info(f"SAS token for device {device_id} expired. Generating new token.")
            expiry = SAS_TOKEN_TIME_LIMIT  # Maintain the original time limit
            sas_token = await create_sas_token(device_id, device_info['primary_key'], expiry)
            await redis_client.hset(device_id, mapping={
                'sas_token': sas_token,
                'token_expiry': str(time.time() + expiry)
            })

        headers = {
            "Authorization": device_info['sas_token'],
            "Content-Type": "application/json"
        }

        telemetry_data = json.dumps({
            'device_id': device_id,
            'message': message
        })

        async with aiohttp_session.post(IOT_HUB_URL.format(device_id=device_id), headers=headers, data=telemetry_data) as response:
            if response.status == 204:
                logging.info(f"Telemetry sent for device {device_id}")
            else:
                logging.error(f"Failed to send telemetry. Status: {response.status}, Response: {await response.text()}")

    except Exception as e:
        logging.error(f"Error sending telemetry for device {device_id}: {e}")

@app.post("/")
async def handle_post_request(data: dict):
    """Handle incoming POST requests, validate JSON, and send telemetry."""
    start_time = time.time()  # Start timing the request
    try:
        if 'device_id' not in data or 'time' not in data:
            raise HTTPException(status_code=400, detail='Invalid packet. Missing device_id or time.')

        device_id = data['device_id']

        device_info = await register_device_on_iot_hub(device_id)
        if not device_info:
            raise HTTPException(status_code=500, detail='Failed to register device.')

        await send_telemetry_to_iot_hub(device_id, data)

        latency = (time.time() - start_time) * 1000  # Calculate latency in ms
        logging.info(f"Request handled in {latency:.2f} ms")

        return JSONResponse(content={'status': 'Telemetry received and sent to IoT Hub.'}, status_code=200)

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail='Invalid JSON format.')
    except Exception as e:
        logging.error(f"Error handling request: {e}")
        raise HTTPException(status_code=500, detail='Internal Server Error')

async def start_redis_connection():
    """Start the Redis connection."""
    global redis_client
    pool = ConnectionPool(host='localhost', port=6379, max_connections=100, decode_responses=True)
    redis_client = redis.Redis(connection_pool=pool)

async def start_aiohttp_session():
    """Start the aiohttp ClientSession."""
    global aiohttp_session
    aiohttp_session = aiohttp.ClientSession()

@app.on_event("startup")
async def startup_event():
    """Start Redis connection and aiohttp session when FastAPI app starts."""
    await start_redis_connection()
    await start_aiohttp_session()

@app.on_event("shutdown")
async def shutdown_event():
    """Close Redis connection and aiohttp session when FastAPI app shuts down."""
    await redis_client.close()
    await aiohttp_session.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9005)
