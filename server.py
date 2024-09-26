import socket
import threading
import logging
import json
from azure.iot.device import ProvisioningDeviceClient, IoTHubDeviceClient, Message

from constant import HOST, PORT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # For Docker logs
)

# Azure IoT DPS and IoT Hub credentials
ID_SCOPE = "0ne00B2BFAE"
DPS_GLOBAL_ENDPOINT = "global.azure-devices-provisioning.net"
IOTHUB_CONNECTION_STRING = "HostName=iothubdevuae.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=TgNmv49DIduLOsnHU7ccaESSOcXnpKu9UAIoTOMlm0s="

# Unique connection number tracker
connection_counter = 0

# Provision device using Azure DPS
def provision_device(device_id):
    provisioning_host = DPS_GLOBAL_ENDPOINT
    registration_id = device_id
    symmetric_key = "Your Symmetric Key for Device"  # You will need to generate a symmetric key for each client

    # Create provisioning client
    provisioning_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host=provisioning_host,
        registration_id=registration_id,
        id_scope=ID_SCOPE,
        symmetric_key=symmetric_key
    )

    # Register the device
    registration_result = provisioning_client.register()
    logging.info(f"Registration result: {registration_result.status}")

    if registration_result.status == 'assigned':
        logging.info(f"Device {device_id} registered to IoT Hub {registration_result.registration_state.assigned_hub}")
        return registration_result.registration_state.assigned_hub, registration_result.registration_state.device_id
    else:
        raise Exception(f"Failed to register device {device_id} with DPS.")

# Send telemetry to IoT Hub
def send_telemetry_to_iot_hub(iothub_device_client, telemetry_data):
    message = Message(json.dumps(telemetry_data))
    iothub_device_client.send_message(message)
    logging.info(f"Sent telemetry data: {telemetry_data}")

# Handle client connection
def handle_client(client_socket, client_address):
    global connection_counter
    connection_counter += 1
    connection_number = connection_counter
    device_id = f"client_{connection_number}"

    # Provision the device via DPS
    try:
        hub_name, device_id = provision_device(device_id)

        # Create IoT Hub client
        iothub_device_client = IoTHubDeviceClient.create_from_connection_string(IOTHUB_CONNECTION_STRING)

        while True:
            data = client_socket.recv(1024)
            if not data:
                break

            # Process the received data
            received_message = data.decode('utf-8')
            logging.info(f"Received from client {device_id}: {received_message}")

            # Encapsulate data into JSON
            telemetry_data = {
                "connection_number": connection_number,
                "client_ip": client_address[0],
                "message": received_message
            }

            # Send telemetry to IoT Hub
            send_telemetry_to_iot_hub(iothub_device_client, telemetry_data)

    except Exception as e:
        logging.error(f"Error handling client {device_id}: {e}")
    finally:
        logging.info(f"Closing connection with {device_id}")
        client_socket.close()

def start_tcp_server():
    # Create and bind a TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server_socket.bind((HOST, PORT))
        logging.info(f"Server started on {HOST}:{PORT}")
    except OSError as e:
        logging.error(f"Failed to bind to {HOST}:{PORT} - {e}")
        return

    server_socket.listen(5)
    logging.info("Server is listening for incoming connections...")

    while True:
        client_socket, client_address = server_socket.accept()
        logging.info(f"Connection established with {client_address}")

        client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        client_thread.start()

if __name__ == "__main__":
    start_tcp_server()
