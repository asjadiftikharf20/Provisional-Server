import socket
import json

SERVER_IP = '0.0.0.0'  # Replace with actual server IP if needed
SERVER_PORT = 8080

def start_tcp_client():
    # Create a TCP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Connect to the server
        client_socket.connect((SERVER_IP, SERVER_PORT))
        print(f"[INFO] Connected to {SERVER_IP}:{SERVER_PORT}")

        # Receive device credentials from the server
        device_credentials = client_socket.recv(1024).decode('utf-8')
        device_info = json.loads(device_credentials)
        
        device_id = device_info.get('device_id')

        if device_id:
            print(f"[INFO] Device registered with IoT Hub: {device_id}")
        else:
            print("[ERROR] Failed to receive device credentials.")
            return

        # Loop for user input and sending telemetry
        while True:
            message = input("Enter a message (type 'exit' or '0' to quit): ")
            if message.lower() == 'exit' or message == '0':
                print("[INFO] Exiting client.")
                break

            # Prepare message in JSON format including the device credentials
            telemetry_data = json.dumps({
                'device_id': device_id,
                'message': message  # Send the message directly, without double encoding
            })

            # Send the message to the server
            client_socket.sendall(telemetry_data.encode('utf-8'))

            # Receive server acknowledgment (optional)
            response = client_socket.recv(1024)
            print(f"[INFO] Received from server: {response.decode('utf-8')}")

    except Exception as e:
        print(f"[ERROR] {e}")
    
    finally:
        # Close the socket connection
        client_socket.close()

if __name__ == "__main__":
    start_tcp_client()
