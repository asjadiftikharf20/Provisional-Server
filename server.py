# server.py

import socket
import logging
from constant import HOST, PORT

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',  # Define log format
    handlers=[logging.StreamHandler()]  # Output logs to console
)

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
    logging.info(f"Server is listening for incoming connections...")

    while True:
        logging.info("Waiting for a connection...")
        
        # Accept client connection (this completes the SYN-SYNACK-ACK handshake)
        client_socket, client_address = server_socket.accept()
        logging.info(f"Connection established with {client_address}")
        
        # After the handshake, send a specific message (like an authentication code)
        auth_message = "1"  # This is the "1" we're sending for authentication
        logging.info(f"Sending authentication message: {auth_message}")
        client_socket.sendall(auth_message.encode('utf-8'))  # Send the "1" as authentication

        try:
            # Now wait to receive data from the client
            while True:
                data = client_socket.recv(1024)
                if data:
                    logging.info(f"Received data: {data.decode('utf-8')}")
                else:
                    break

        except Exception as e:
            logging.error(f"Error while receiving data from {client_address}: {e}")
        
        finally:
            logging.info(f"Closing connection with {client_address}")
            client_socket.close()

if __name__ == "__main__":
    start_tcp_server()
