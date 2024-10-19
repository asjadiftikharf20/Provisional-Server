import asyncio
import logging
import json
import binascii
import struct
from urllib.parse import urlparse, parse_qs
from constants8e import *
from fastapi import FastAPI, Query, HTTPException
import os
from parameters import *
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
connections = {}
devices = {}
connected_clients = {}
device_data_store = {}

app = FastAPI()


async def handle_device_commands(reader, writer, imei):
    try:
        data = await reader.read(1024)
        if data:
            hex_data = data.hex()
            logger.info(f"Data received from device '{imei}': {hex_data}")

            # Store raw hex data for reference
            if imei not in device_data_store:
                device_data_store[imei] = []
            device_data_store[imei].append(hex_data)

            # Check and parse the received data
            if codec_8e_checker(hex_data):
                logger.info("Processing codec 8e data...")
                parsed_data = codec_8e_parser(hex_data, imei, {})
                if parsed_data:
                    device_data_store[imei].append(parsed_data)
                    await send_parsed_data_to_client(writer, parsed_data)
            elif codec_12_checker(hex_data):
                logger.info("Processing codec 12 data...")
                parsed_data = parse_response_message(hex_data, imei)
                if parsed_data:
                    device_data_store[imei].append(parsed_data)
                    logger.info(f"Parsed codec 12 data: {parsed_data}")
                    await send_parsed_data_to_client(writer, parsed_data)
            return data
        else:
            logger.warning("No data received.")
            return None
    except Exception as e:
        logger.error(f"Error in handle_device_commands: {e}")
        return None


async def send_parsed_data_to_client(writer, parsed_data):
    try:
        response_message = json.dumps(parsed_data).encode("utf-8")
        writer.write(response_message)  # Send parsed data back to the TCP client
        await writer.drain()
        logger.info(f"Sent parsed data to the client: {parsed_data}")
    except Exception as e:
        logger.error(f"Error sending parsed data to the client: {e}")


def parse_response_message(hex_data, device_id):
    """
    Parses the hexadecimal data received from the TCP server.

    Args:
        hex_data (str): The hexadecimal string received from the server.
        device_id (str): The ID of the device.

    Returns:
        dict: Parsed data containing device_id and response_data.
    """
    try:
        data = bytes.fromhex(hex_data)
        preamble = data[0:4]
        data_size = data[4:8]
        response_size = data[11:15]
        response_size_value = struct.unpack("!I", response_size)[0]
        response_data = data[15 : 15 + response_size_value]
        response_string = response_data.decode("utf-8", errors="ignore")

        return {
            "device_id": device_id,
            "response_data": response_string,
        }
    except Exception as e:
        logger.error(f"Error parsing message: {e}")
        return None


async def handle_device_registration(imei, writer):
    connections[imei] = writer  # Add the device's writer to the connections list
    device_data_store[imei] = []  # Initialize storage for the device's data
    logger.info(f"Device '{imei}' connected.")
    await send_acknowledgment(writer)


async def send_acknowledgment(writer):
    try:
        ack_response = bytes([0x01])  # Simple acknowledgment byte
        writer.write(ack_response)
        await writer.drain()
        logger.info("Acknowledgment sent to the device.")
    except Exception as e:
        logger.error(f"Error sending acknowledgment: {e}")


async def handle_connection(reader, writer):
    addr = writer.get_extra_info("peername")
    device = None  # Initialize the device object

    try:
        while True:
            data = await reader.read(1280)
            if not data:
                break

            hex_data = data.hex()
            logger.info(f"Received hex data: {hex_data}")

            if imei_checker(hex_data):
                device_imei = ascii_imei_converter(hex_data)
                device = Device(device_imei, writer)
                connections[device_imei] = device
                logger.info(f"Connected to device with IMEI: {device_imei}")
                await send_acknowledgment(writer)

            # Process HTTP-like requests
            elif hex_data.startswith("504f5354202f73656e642d646174613f69643d"):
                logger.info("HTTP-like request detected")
                ascii_data = data.decode("utf-8", errors="ignore").strip()
                headers = ascii_data.split("\r\n")
                request_line = headers[0]
                original_request_url = request_line.split(" ")[1]
                logger.info(f"Original request URL: {original_request_url}")

                parsed_url = urlparse(original_request_url)
                query_params = parse_qs(parsed_url.query)
                extracted_device_id = query_params.get("id", [None])[0]
                command = query_params.get("command", [None])[0]

                logger.info(
                    f"Extracted device ID: {extracted_device_id}, Command: {command}"
                )

                if extracted_device_id and command:
                    device = connections.get(extracted_device_id)
                    if device:
                        logger.info(
                            f"Command '{command}' received for device '{device.imei}'."
                        )
                        if command == "getinfo":
                            logger.info(
                                f"Detected 'getinfo' command for device '{device.imei}'."
                            )
                            response_data = await send_getinfo_command(
                                device.imei, devices[device.imei]
                            )
                            if response_data:
                                response_message = json.dumps(response_data).encode(
                                    "utf-8"
                                )
                                writer.write(response_message)
                                await writer.drain()
                        elif command == "getio":
                            logger.info(
                                f"Detected 'getio' command for device '{device.imei}'."
                            )
                            response_data = await send_getio_command(
                                device.imei, devices[device.imei]
                            )
                            if response_data:
                                response_message = json.dumps(response_data).encode(
                                    "utf-8"
                                )
                                writer.write(response_message)
                                await writer.drain()
                    else:
                        logger.warning(
                            f"Device ID '{extracted_device_id}' not found in connections."
                        )
                continue

            # Process codec 8e data
            elif codec_8e_checker(hex_data.replace(" ", "")):
                if device:
                    logger.info("Processing codec 8e data...")
                    parsed_data = codec_8e_parser(hex_data, device.imei, {})
                    if parsed_data:
                        if device.imei not in device_data_store:
                            device_data_store[device.imei] = []
                        device_data_store[device.imei].append(parsed_data)

            # Process codec 12 data
            elif codec_12_checker(hex_data.replace(" ", "")):
                if device:
                    logger.info("Processing codec 12 data...")
                    parsed_data = parse_response_message(hex_data, device.imei)
                    if parsed_data:
                        if device.imei not in device_data_store:
                            device_data_store[device.imei] = []
                        device_data_store[device.imei].append(parsed_data)
                        logger.info(
                            f"Stored codec 12 data for device {device.imei}: {parsed_data}"
                        )

                        # Send parsed data back to the TCP client
                        await send_parsed_data_to_client(writer, parsed_data)

    except Exception as e:
        logger.error(f"Error in handle_connection: {e}")
    finally:
        if device:
            logger.info(f"Device '{device.imei}' disconnected.")
            del connections[device.imei]
            del devices[device.imei]
            if device.imei in device_data_store:
                del device_data_store[device.imei]
            else:
                logger.warning(
                    f"Device '{device.imei}' not found in data store during disconnection."
                )


@app.post("/send-data")
async def send_data(id: str = Query(...), command: str = Query(...)):
    logger.info(f"Received request for id: {id}, command: {command}")

    try:
        # Find the device connection (writer) for the given ID
        if id not in devices:
            raise HTTPException(status_code=404, detail=f"Device {id} not connected")

        writer = devices[id]

        # Send the command to the device
        await send_command_to_device(writer, command)

        # Wait for the device to respond and store the parsed data
        await asyncio.sleep(3)  # Adding a slight delay to ensure data is processed

        # Retrieve the parsed response for the device
        if id in device_data_store and device_data_store[id]:
            parsed_response = device_data_store[id][-1]  # Latest parsed data
        else:
            parsed_response = {"error": "No response from device"}

        # Return the parsed data as the API response
        return {"device_id": id, "command": command, "parsed_data": parsed_response}

    except Exception as e:
        logger.error(f"Device Not Connected: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to send command to the device"
        )


async def send_command_to_device(writer, command):
    try:
        # Prepare and send the command
        command_bytes = command.encode("utf-8")  # Assuming command is in ASCII
        writer.write(command_bytes)
        await writer.drain()
        logger.info(f"Command '{command}' sent to the device.")
    except Exception as e:
        logger.error(f"Error sending command to the device: {e}")
        raise HTTPException(status_code=500, detail="Failed to send command")


async def tcp_server():
    """
    Starts the TCP server to listen for incoming connections.
    """
    server = await asyncio.start_server(handle_connection, "127.0.0.1", 9000)
    logger.info("TCP Server started and listening for connections...")

    async with server:
        await server.serve_forever()


async def send_getinfo_command(device_imei, writer):
    getinfo_command = b"\x00\x00\x00\x0F\x0C\x01\x05\x00\x00\x00\x07\x67\x65\x74\x69\x6E\x66\x6F\x01\x00\x00\x43\x12"

    try:
        logger.info(
            f"'send_getinfo_command' function called for device '{device_imei}'."
        )
        # Send the command to get information
        writer.write(getinfo_command)
        await writer.drain()

        await asyncio.sleep(2)  # Wait for response

        # Check if there's data for the device in the data store
        if device_imei in device_data_store and device_data_store[device_imei]:
            command_data_hex = device_data_store[device_imei][-1]

            # Ensure command_data_hex is a string before parsing
            if isinstance(command_data_hex, str):
                parsed_data = parse_response_message(command_data_hex, device_imei)

                if parsed_data:
                    # Prepare the response data as a JSON string
                    response_data = {
                        "device_id": device_imei,
                        "response_data": parsed_data,  # Assuming parsed_data is already in dict format
                    }
                    print(f"parsed reponse after getinfo{response_data}")
                    return response_data
    except Exception as e:
        logger.error(f"Error in send_getinfo_command: {e}")
    return None


async def send_getio_command(device_imei, writer):
    getio_command = b"\x00\x00\x00\x00\x00\x00\x00\r\x0c\x01\x05\x00\x00\x00\x05getio\x01\x00\x00\x00"

    try:
        logger.info(f"'send_getio_command' function called for device '{device_imei}'.")
        writer.write(getio_command)
        await writer.drain()
        logger.info(f"Sending 'getio' command to device '{device_imei}'.")

        await asyncio.sleep(1)  # Wait for the device to respond

        if device_imei in device_data_store and device_data_store[device_imei]:
            command_data_hex = device_data_store[device_imei][-1]

            logger.info(
                f"send_getio_command: Received data in HEX from store: {command_data_hex}"
            )

            parsed_data = parse_response_message(command_data_hex, device_imei)
            if parsed_data:
                # Prepare the response data as a JSON string
                response_data = {
                    "device_id": device_imei,
                    "response_data": parsed_data,  # Assuming parsed_data is already in dict format
                }
                return response_data
            else:
                logger.warning("Parsed data is None. Skipping response to client.")
        else:
            logger.warning(
                f"No response found for device '{device_imei}' in the data store."
            )
    except Exception as e:
        logger.error(f"Error in send_getio_command: {e}")
    return None


async def tcp_server():
    """
    Starts the TCP server to listen for incoming connections.
    """
    server = await asyncio.start_server(handle_connection, "127.0.0.1", 9000)
    logger.info("TCP Server started and listening for connections...")

    async with server:
        await server.serve_forever()


def codec_8e_checker(hex_data):
    return hex_data[16:18] == "8E"


def codec_12_checker(hex_data):
    return hex_data[16:18] == "0c"


class Device:
    def __init__(self, imei, writer):
        self.imei = imei
        self.writer = writer
        # Store the device connection
        connections[imei] = True
        devices[imei] = writer

    async def send_acknowledgment(self):
        ack_response = bytes([0x01])
        self.writer.write(ack_response)
        await self.writer.drain()

    async def handle_data(self, data):
        """Process and handle data for the specific device."""
        hex_data = data.hex()

        if imei_checker(hex_data):
            self.imei = ascii_imei_converter(hex_data)
            print(f"Connected to device with IMEI: {self.imei}")
            await self.send_acknowledgment()
        elif codec_8e_checker(hex_data.replace(" ", "")):
            codec_8e_parser(hex_data.replace(" ", ""), self.imei, {})
            record_response = (1).to_bytes(4, byteorder="big")
            self.writer.write(record_response)
            await self.writer.drain()


def imei_checker(hex_imei):
    imei_length = int(hex_imei[:4], 16)
    if imei_length != len(hex_imei[4:]) / 2:
        return False
    ascii_imei = ascii_imei_converter(hex_imei)
    return ascii_imei.isnumeric() and len(ascii_imei) == 15


def ascii_imei_converter(hex_imei):
    return bytes.fromhex(hex_imei[4:]).decode()


def codec_8e_checker(codec8_packet):
    if str(codec8_packet[16:18]).upper() != "8E":
        return False
    else:
        return codec8_packet


def codec_parser_trigger(codec8_packet, device_imei, props):
    try:
        return codec_8e_parser(codec8_packet.replace(" ", ""), device_imei, props)
    except Exception:
        return 0


def codec_8e_parser(codec_8E_packet, device_imei, props):
    def sorting_hat(key, value):
        description = TELTONIKA_IO_MAPPING.get(key, f"{key}")
        return {description: value}

    io_dict_raw = {
        "DeviceID": device_imei,
        "_raw_data__": codec_8E_packet,
    }

    data_field_length = int(codec_8E_packet[8:16], 16)
    # number_of_records = int(codec_8E_packet[18:20], 16)
    # print(f"number of records = {number_of_records}")
    codec_type = str(codec_8E_packet[16 : 16 + 2])

    record_number = 1
    avl_data_start = codec_8E_packet[20:]
    data_field_position = 0
    json_records = []
    records = []
    while data_field_position < (2 * data_field_length - 6):
        io_dict = {
            "DeviceID": device_imei,
        }
        data_step = 4

        timestamp = avl_data_start[data_field_position : data_field_position + 16]
        device_time_utc, device_time_local = device_time_stamper(timestamp)

        io_dict["t"] = device_time_local  # Store as a string

        reception_time_utc, reception_time_local = set_reception_time()

        io_dict["receptionTime "] = reception_time_local

        reception_time_utc_dt = datetime.datetime.strptime(
            reception_time_utc, "%H:%M:%S %d-%m-%Y"
        )
        device_time_utc_dt = datetime.datetime.strptime(
            device_time_utc, "%H:%M:%S %d-%m-%Y"
        )

        # Calculate time difference in seconds
        time_difference = abs(
            (reception_time_utc_dt - device_time_utc_dt).total_seconds()
        )
        # Set RTP value based on the time difference
        rtp = 0 if time_difference > 60 else 1
        io_dict["rtp"] = rtp

        data_field_position += len(timestamp)

        priority = avl_data_start[data_field_position : data_field_position + 2]
        # io_dict["priority"] = int(priority, 16)
        # print(f"record priority = {int(priority, 16)}")
        data_field_position += len(priority)

        longitude = avl_data_start[data_field_position : data_field_position + 8]
        io_dict["longitude"] = coordinate_formater(longitude)
        data_field_position += len(longitude)

        latitude = avl_data_start[data_field_position : data_field_position + 8]
        io_dict["latitude"] = coordinate_formater(latitude)
        data_field_position += len(latitude)

        altitude = avl_data_start[data_field_position : data_field_position + 4]
        io_dict["altitude"] = int(altitude, 16)
        data_field_position += len(altitude)

        angle = avl_data_start[data_field_position : data_field_position + 4]
        io_dict["angle"] = int(angle, 16)
        data_field_position += len(angle)

        satelites = avl_data_start[data_field_position : data_field_position + 2]
        io_dict["satelites"] = int(satelites, 16)
        data_field_position += len(satelites)

        speed = avl_data_start[data_field_position : data_field_position + 4]
        io_dict["speed"] = int(speed, 16)
        data_field_position += len(speed)

        event_io_id = avl_data_start[
            data_field_position : data_field_position + data_step
        ]
        io_dict["eventID"] = int(event_io_id, 16)
        # print(f"event ID = {int(event_io_id, 16)}")
        data_field_position += len(event_io_id)

        total_io_elements = avl_data_start[
            data_field_position : data_field_position + data_step
        ]
        total_io_elements_parsed = int(total_io_elements, 16)

        data_field_position += len(total_io_elements)

        byte1_io_number = avl_data_start[
            data_field_position : data_field_position + data_step
        ]
        byte1_io_number_parsed = int(byte1_io_number, 16)
        data_field_position += len(byte1_io_number)

        if byte1_io_number_parsed > 0:
            i = 1
            while i <= byte1_io_number_parsed:
                key = avl_data_start[
                    data_field_position : data_field_position + data_step
                ]
                data_field_position += len(key)
                value = avl_data_start[data_field_position : data_field_position + 2]
                key_int = int(key, 16)
                value_int = int(value, 16)
                description = TELTONIKA_IO_MAPPING.get(
                    int(key, 16), f"Unknown IO {key}"
                )
                io_dict[description] = int(value, 16)
                data_field_position += len(value)

                i += 1
        else:
            pass

        byte2_io_number = avl_data_start[
            data_field_position : data_field_position + data_step
        ]
        byte2_io_number_parsed = int(byte2_io_number, 16)
        data_field_position += len(byte2_io_number)

        if byte2_io_number_parsed > 0:
            i = 1
            while i <= byte2_io_number_parsed:
                key = avl_data_start[
                    data_field_position : data_field_position + data_step
                ]
                data_field_position += len(key)

                value = avl_data_start[data_field_position : data_field_position + 4]
                key_int = int(key, 16)
                value_int = int(value, 16)
                description = TELTONIKA_IO_MAPPING.get(
                    int(key, 16), f"Unknown IO {key}"
                )
                io_dict[description] = int(value, 16)
                data_field_position += len(value)

                i += 1
        else:
            pass

        byte4_io_number = avl_data_start[
            data_field_position : data_field_position + data_step
        ]
        byte4_io_number_parsed = int(byte4_io_number, 16)
        data_field_position += len(byte4_io_number)

        if byte4_io_number_parsed > 0:
            i = 1
            while i <= byte4_io_number_parsed:
                key = avl_data_start[
                    data_field_position : data_field_position + data_step
                ]
                data_field_position += len(key)

                value = avl_data_start[data_field_position : data_field_position + 8]
                key_int = int(key, 16)
                value_int = int(value, 16)
                description = TELTONIKA_IO_MAPPING.get(
                    int(key, 16), f"Unknown IO {key}"
                )
                io_dict[description] = int(value, 16)
                data_field_position += len(value)
                i += 1
        else:
            pass

        byte8_io_number = avl_data_start[
            data_field_position : data_field_position + data_step
        ]
        byte8_io_number_parsed = int(byte8_io_number, 16)
        data_field_position += len(byte8_io_number)

        if byte8_io_number_parsed > 0:
            i = 1
            while i <= byte8_io_number_parsed:
                key = avl_data_start[
                    data_field_position : data_field_position + data_step
                ]
                data_field_position += len(key)

                value = avl_data_start[data_field_position : data_field_position + 16]
                key_int = int(key, 16)
                value_int = int(value, 16)
                description = TELTONIKA_IO_MAPPING.get(
                    int(key, 16), f"Unknown IO {key}"
                )
                io_dict[description] = int(value, 16)
                data_field_position += len(value)

                i += 1
        else:
            pass

        if codec_type.upper() == "8E":

            byteX_io_number = avl_data_start[
                data_field_position : data_field_position + 4
            ]
            byteX_io_number_parsed = int(byteX_io_number, 16)
            data_field_position += len(byteX_io_number)

            if byteX_io_number_parsed > 0:
                i = 1
                while i <= byteX_io_number_parsed:
                    key = avl_data_start[data_field_position : data_field_position + 4]
                    data_field_position += len(key)

                    value_length = avl_data_start[
                        data_field_position : data_field_position + 4
                    ]
                    data_field_position += 4
                    value = avl_data_start[
                        data_field_position : data_field_position
                        + (2 * (int(value_length, 16)))
                    ]
                    io_dict[int(key, 16)] = sorting_hat(int(key, 16), value)
                    data_field_position += len(value)
                    key_int = int(key, 16)
                    value_int = int(value, 16)
                    description = TELTONIKA_IO_MAPPING.get(
                        int(key, 16), f"Unknown IO {key}"
                    )
                    io_dict[description] = int(value, 16)
                    data_field_position += len((value, 16))
                    i += 1
            else:
                pass

        else:
            pass

        json_output = json.dumps(io_dict)
        json_records.append(json_output)

        print(f"Record {record_number} (Parsed Packet): {json_output}")

        # Increment to the next record
        record_number += 1

    if props == "SERVER":
        total_records_parsed = record_number - 1  # Total processed records

        # # Send each record to the API individually
        # for json_output in json_records:
        #     try:
        #         response = requests.post(
        #             # API_ENDPOINT,
        #             timeout=30,
        #             data=json_output,
        #             headers={"Content-Type": "application/json"},
        #         )
        #         if response.status_code == 200:
        #             print(f"Record successfully sent to IoT Hub")
        #         else:
        #             print(
        #                 f"Failed to send record to API. Status code: {response.status_code}"
        #             )
        #     except Exception as e:
        #         print(f"Error occurred while sending record to API: {e}")

        # Return the number of total processed records
        return {}, total_records_parsed
    else:
        return 0


def coordinate_formater(hex_coordinate):
    coordinate = int(hex_coordinate, 16)
    if coordinate & (1 << 31):
        new_int = coordinate - 2**32
        dec_coordinate = new_int / 1e7
    else:
        dec_coordinate = coordinate / 10000000
    return dec_coordinate


def time_stamper_for_json():
    """Returns two timestamps: local server time and current UTC time."""
    current_server_time = datetime.datetime.now(datetime.timezone.utc)
    server_time_stamp_local = current_server_time.astimezone().strftime(
        "%H:%M:%S %d-%m-%Y"
    )
    server_time_stamp_utc = current_server_time.strftime("%H:%M:%S %d-%m-%Y")
    return server_time_stamp_local, server_time_stamp_utc


def device_time_stamper(timestamp):
    """Takes a timestamp from the device (hexadecimal format) and converts it into both UTC and local time."""
    timestamp_ms = int(timestamp, 16) / 1000
    timestamp_utc = datetime.datetime.fromtimestamp(timestamp_ms, datetime.timezone.utc)
    timestamp_local = (
        timestamp_utc.astimezone()
    )  # Automatically converts to the local time zone
    # Formatting timestamps separately for clarity
    formatted_timestamp_local = timestamp_local.strftime("%H:%M:%S %d-%m-%Y")
    formatted_timestamp_utc = timestamp_utc.strftime("%H:%M:%S %d-%m-%Y")
    return formatted_timestamp_local, formatted_timestamp_utc


def set_reception_time():
    """Returns the current time for time in both UTC and local formats."""
    current_time_utc = datetime.datetime.now(datetime.timezone.utc)
    formatted_reception_time_utc = current_time_utc.strftime("%H:%M:%S %d-%m-%Y")
    formatted_reception_time_local = current_time_utc.astimezone().strftime(
        "%H:%M:%S %d-%m-%Y"
    )
    # Return the reception time in a tuple format
    return (formatted_reception_time_utc, formatted_reception_time_local)


async def main():
    """
    Main function to start both the TCP server and the FastAPI application.
    """

    await asyncio.gather(
        tcp_server(),
        # Run FastAPI app in another thread
        asyncio.to_thread(uvicorn.run, app, host="0.0.0.0", port=9000),
    )


if __name__ == "__main__":
    asyncio.run(main())