# client_class.py

import json

class Client:
    def __init__(self, client_id, ip_address, connection_number):
        self.client_id = client_id
        self.ip_address = ip_address
        self.connection_number = connection_number

    def to_json(self, message):
        """Encapsulate the client's info and message in JSON format"""
        return json.dumps({
            'client_id': self.client_id,
            'ip_address': self.ip_address,
            'connection_number': self.connection_number,
            'message': message
        })
