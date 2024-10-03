import aiohttp
import asyncio
import json
from datetime import datetime
import time

# Set the total number of clients you want to send to
TOTAL_CLIENTS = 500  # Change this value to test with more or fewer clients

async def send_post_request(device_id, session):
    """Send a POST request to the server with telemetry data."""
    url = "http://0.0.0.0:8080"
    timestamp = datetime.utcnow().isoformat() + "Z"  # Current UTC time in ISO format
    payload = {
        "device_id": device_id,
        "time": timestamp,
        "message": "Sample telemetry message"
    }

    start_time = time.time()  # Start timing the individual request
    async with session.post(url, json=payload) as response:
        latency = (time.time() - start_time) * 1000  # Calculate individual request latency in ms
        if response.status == 200:
            print(f"Successfully sent data for {device_id}: {await response.json()} | Latency: {latency:.2f} ms")
        else:
            print(f"Failed to send data for {device_id}: {response.status} {await response.text()} | Latency: {latency:.2f} ms")
        return latency  # Return the individual request latency

async def main():
    start_time = time.time()  # Start timing the overall execution
    total_latencies = []  # List to store latencies for each device
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(1, TOTAL_CLIENTS + 1):  # From 1 to TOTAL_CLIENTS
            device_id = f"client_{i}"
            tasks.append(send_post_request(device_id, session))

        # Wait for all POST requests to complete and collect latencies
        total_latencies = await asyncio.gather(*tasks)

    total_latency = (time.time() - start_time) * 1000  # Calculate total latency in ms
    average_latency = total_latency / TOTAL_CLIENTS  # Calculate average latency per device

    print(f"\nTotal latency for sending {TOTAL_CLIENTS} POST requests: {total_latency:.2f} ms")
    print(f"Average latency per device: {average_latency:.2f} ms")

if __name__ == "__main__":
    asyncio.run(main())
