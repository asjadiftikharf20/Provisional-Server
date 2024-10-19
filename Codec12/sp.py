import socket
import binascii
import time


def tcp_client(host, port):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create a TCP/IP socket
    client.connect((host, port))  # Connect the socket to the server

    # Step 1: Send the IMEI number (000F + IMEI)
    imei = "000F333536333037303432343431303133"  # Initial IMEI example
    imei_hex = binascii.unhexlify(imei)  # Convert IMEI to bytes

    client.send(imei_hex)
    print(f"Sent IMEI: {imei}")

    # Step 2: Receive acknowledgment (01) from the server
    ack = client.recv(1024).hex()
    print(f"Received acknowledgment from server: {ack}")

    if ack == "01":
        print("Acknowledgment received, starting data transmission...")

        # Step 3: Prepare AVL data to send every 5 seconds
        avl_data = "000000000000004A8E010000016B412CEE000100000000000000000000000000000000010005000100010100010011001D00010010015E2C880002000B000000003544C87A000E000000001DD7E06A00000100002994"
        avl_data_hex = binascii.unhexlify(avl_data)

        while True:
            client.send(avl_data_hex)
            print(f"Sent AVL data: {avl_data}")

            # Step 4: Wait for a command from the server
            server_command = client.recv(1024)
            try:
                server_command_decoded = server_command.decode("utf-8")
                print(f"Received command from server: {server_command_decoded}")

                if "getinfo" in server_command_decoded:
                    # Send hex data for 'getinfo' command
                    hex_data = bytes.fromhex(
                        "00000000000000900C010600000088494E493A323031392F372F323220373A3232205254433A323031392F372F323220373A3533205253543A32204552523A312053523A302042523A302043463A302046473A3020464C3A302054553A302F302055543A3020534D533A30204E4F4750533A303A3330204750533A31205341543A302052533A332052463A36352053463A31204D443A30010000C78F"
                    )
                    client.sendall(hex_data)
                    print(f"Sent hex data to server for 'getinfo': {hex_data.hex()}")
                elif "getio" in server_command_decoded:
                    # Send hex data for 'getinfo' command
                    hex_data = bytes.fromhex(
                        "00000000000000370C01060000002F4449313A31204449323A30204449333A302041494E313A302041494E323A313639323420444F313A3020444F323A3101000066E3"
                    )
                    client.sendall(hex_data)
                    print(f"Sent hex data to server for 'getio': {hex_data.hex()}")

            except UnicodeDecodeError:
                print("Received non-UTF-8 data from server, processing as hex...")
                print(f"Hex data: {server_command.hex()}")

            time.sleep(5)  # Sleep for 5 seconds before sending the next data
    else:
        print("Failed to receive acknowledgment. Server response:", ack)

    client.close()


# Main entry point
if __name__ == "__main__":
    tcp_client("127.0.0.1", 9000)