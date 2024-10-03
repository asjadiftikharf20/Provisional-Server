import socket
import logging
import json
import time
import threading
from azure.iot.device import IoTHubDeviceClient, Message
from azure.iot.hub import IoTHubRegistryManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# IoT Hub connection string (replace with your actual connection string)
IOTHUB_CONNECTION_STRING = "HostName=iothubdevuae.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=TgNmv49DIduLOsnHU7ccaESSOcXnpKu9UAIoTOMlm0s="

# Store registered devices and their credentials (in-memory storage for now, can be DB for real-world scenario)
registered_devices = {}

def register_device_on_iot_hub(client_id):
    registry_manager = IoTHubRegistryManager(IOTHUB_CONNECTION_STRING)

    # Start timing the device registration process
    start_time = time.time()

    # Check if the device is already registered
    try:
        device_info = registry_manager.get_device(client_id)
        primary_key = device_info.authentication.symmetric_key.primary_key
        secondary_key = device_info.authentication.symmetric_key.secondary_key
        logging.info(f"Device {client_id} already registered. Fetching existing credentials.")

        # Stop timing and calculate the time taken
        elapsed_time = time.time() - start_time
        logging.info(f"Time taken to fetch existing credentials for {client_id}: {elapsed_time:.4f} seconds")

        return primary_key, secondary_key

    except Exception as e:
        logging.info(f"Device {client_id} not found. Registering a new device.")

    # If not registered, create a new device with generated symmetric keys
    try:
        device = registry_manager.create_device_with_sas(client_id, None, None, None)
        primary_key = device.authentication.symmetric_key.primary_key
        secondary_key = device.authentication.symmetric_key.secondary_key

        # Store credentials for reuse
        registered_devices[client_id] = (primary_key, secondary_key)

        logging.info(f"Device {client_id} registered with IoT Hub. Primary Key: {primary_key}")

        # Stop timing and calculate the time taken for registration
        elapsed_time = time.time() - start_time
        logging.info(f"Time taken to register device {client_id}: {elapsed_time:.4f} seconds")

        return primary_key, secondary_key

    except Exception as e:
        logging.error(f"Failed to register device {client_id}: {e}")
        return None, None

def send_telemetry_to_iot_hub(device_id, message):
    try:
        # Fetch the primary key for the device
        primary_key = registered_devices[device_id][0]
        
        # Log the primary key without sending it to the client
        logging.info(f"Primary key for device {device_id}: {primary_key}")
        
        # Create the IoTHubDeviceClient instance using the device credentials
        device_client = IoTHubDeviceClient.create_from_symmetric_key(
            symmetric_key=primary_key,
            hostname="iothubdevuae.azure-devices.net",  # Update this with your IoT Hub Hostname
            device_id=device_id,
        )
        
        # Connect the client
        device_client.connect()

        # Prepare and send the telemetry message to IoT Hub (client ID and message only)
        telemetry_message = Message(json.dumps({
            'device_id': device_id,
            'message': message
        }))
        device_client.send_message(telemetry_message)
        logging.info(f"Telemetry message sent: {telemetry_message}")

        # Disconnect the client after sending
        device_client.disconnect()

    except Exception as e:
        logging.error(f"Failed to send telemetry from {device_id}: {e}")

def handle_client_connection(client_socket, client_address):
    logging.info(f"Connection established with {client_address}")

    # Assign a client ID (for example: client_1, client_2, etc.)
    client_id = f"client_{client_address[1]}"

    # Register the device on IoT Hub and get credentials or use existing ones
    primary_key, secondary_key = register_device_on_iot_hub(client_id)

    if primary_key:
        # Send only the client ID back to the client, not the primary key
        client_info = json.dumps({
            'device_id': client_id
        })
        client_socket.sendall(client_info.encode('utf-8'))
        logging.info(f"Sent client_id {client_id} to client {client_address}")
    else:
        logging.error(f"Error handling client {client_id}: Failed to register or fetch device credentials")
        client_socket.close()
        return

    # Keep the connection open, waiting for telemetry
    try:
        while True:
            data = client_socket.recv(1024)
            if data:
                message = data.decode('utf-8')
                logging.info(f"Received data from {client_id}: {message}")

                # Send the telemetry (client ID and message) to IoT Hub
                send_telemetry_to_iot_hub(client_id, message)

                # Send a response back to the client (optional)
                client_socket.sendall(f"Telemetry received: {message}".encode('utf-8'))
            else:
                # No data received means the client closed the connection
                logging.info(f"Client {client_id} disconnected.")
                break

    except Exception as e:
        logging.error(f"Error receiving data from {client_id}: {e}")
    
    finally:
        logging.info(f"Closing connection with {client_id}")
        client_socket.close()


def start_tcp_server():
    # Create and bind a TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        server_socket.bind(('0.0.0.0', 8080))
        logging.info("Server started on 0.0.0.0:8080")
    except OSError as e:
        logging.error(f"Failed to bind: {e}")
        return

    server_socket.listen(100)  # Listen for up to 100 connections
    logging.info("Server is listening for incoming connections...")

    while True:
        logging.info("Waiting for a connection...")
        
        # Accept client connection
        client_socket, client_address = server_socket.accept()

        # Handle each client in a new thread
        client_thread = threading.Thread(target=handle_client_connection, args=(client_socket, client_address))
        client_thread.start()

if __name__ == "__main__":
    start_tcp_server()
