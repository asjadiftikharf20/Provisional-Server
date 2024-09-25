# client.py

import socket

SERVER_IP = '0.0.0.0'  # Change this to the correct server IP if needed
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

        # Loop to take input from the user and send data to the server
        while True:
            message = input("Enter a message to send to the server (type 'exit' or '0' to quit): ")

            if message.lower() == 'exit' or message == '0':
                print("[INFO] Exiting and closing connection...")
                break

            # Send the message to the server
            client_socket.sendall(message.encode('utf-8'))

            # Optionally receive a response from the server
            # response = client_socket.recv(1024)
            # if response:
            #     print(f"[INFO] Received from server: {response.decode('utf-8')}")


    except Exception as e:
        print(f"[ERROR] An error occurred: {e}")

    finally:
        # Close the connection when done
        client_socket.close()
        print("[INFO] Connection closed.")

if __name__ == "__main__":
    start_tcp_client()
