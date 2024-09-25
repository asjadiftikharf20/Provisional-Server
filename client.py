# client.py

import socket

SERVER_IP = '0.0.0.0'
SERVER_PORT = 8080

def start_tcp_client():
    # Create a TCP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Initiate the connection to the server (this sends the SYN packet)
        print(f"[INFO] Sending SYN packet to {SERVER_IP}:{SERVER_PORT}...")
        client_socket.connect((SERVER_IP, SERVER_PORT))  # SYN-ACK handshake occurs here
        print("[INFO] Connection established (SYN-ACK received).")

        # After connection, expect to receive authentication message from the server
        auth_message = client_socket.recv(1024)
        print(f"[INFO] Received authentication message from server: {auth_message.decode('utf-8')}")
        
        # Now you can send data to the server
        message = "Hello, TCP Server! This is a message from the client."
        print(f"[INFO] Sending message: {message}")
        client_socket.sendall(message.encode('utf-8'))

        # Receive response (optional)
        response = client_socket.recv(1024)
        print(f"[INFO] Received from server: {response.decode('utf-8')}")
    
    finally:
        print("[INFO] Closing connection to the server.")
        client_socket.close()

if __name__ == "__main__":
    start_tcp_client()
