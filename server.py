# server.py

import socket
from constant import HOST, PORT

def start_tcp_server():
    # Create and bind a TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    print(f"Server started on {HOST}:{PORT}")
    server_socket.listen(5)

    while True:
        print("Waiting for a connection...")
        
        # Accept client connection (this completes the SYN-SYNACK-ACK handshake)
        client_socket, client_address = server_socket.accept()
        print(f"[INFO] Connection established with {client_address}")
        
        # After the handshake, send a specific message (like an authentication code)
        auth_message = "1"  # This is the "1" we're sending for authentication
        print(f"[INFO] Sending authentication message: {auth_message}")
        client_socket.sendall(auth_message.encode('utf-8'))  # Send the "1" as authentication

        try:
            # Now wait to receive data from the client
            while True:
                data = client_socket.recv(1024)
                if data:
                    print(f"[INFO] Received data: {data.decode('utf-8')}")
                else:
                    break

        finally:
            print(f"[INFO] Closing connection with {client_address}")
            client_socket.close()

if __name__ == "__main__":
    start_tcp_server()
