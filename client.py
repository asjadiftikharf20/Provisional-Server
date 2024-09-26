# client.py

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

        # Receive connection number from the server
        connection_number = client_socket.recv(1024).decode('utf-8')
        print(f"[INFO] Assigned connection number: {connection_number}")

        client_id = f'client_{connection_number}'

        # Loop for user input
        while True:
            message = input("Enter a message (type 'exit' or '0' to quit): ")
            if message.lower() == 'exit' or message == '0':
                print("[INFO] Exiting client.")
                break

            # Prepare message in JSON format
            client_info = json.dumps({
                'client_id': client_id,
                'connection_number': connection_number,
                'message': message
            })

            # Send the message
            client_socket.sendall(client_info.encode('utf-8'))

            # Receive and print the server's response
            response = client_socket.recv(1024)
            print(f"[INFO] Received from server: {response.decode('utf-8')}")

    finally:
        # Close the socket connection
        client_socket.close()

if __name__ == "__main__":
    start_tcp_client()
