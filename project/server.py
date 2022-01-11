import socket
import threading
import argparse
import queue
from typing import Tuple, Optional
import pickle
import json


class Server:
    """
    Multithread tcp socket server for managing simple FTP.
    """

    HEADER_LENGTH = 10

    def __init__(self):
        args = Server.get_args()
        self.host = args.host
        self.port = args.port

        # Buffer for storing file paths of files currently being uploaded to the server
        self.files_in_transfer_buffer = list()  # Not thread-safe -> critical section needed
        self.files_in_transfer_mutex = threading.Lock()

    @staticmethod
    def get_args() -> argparse.Namespace:
        parser = argparse.ArgumentParser(description='Run simple FTP server.')
        parser.add_argument('-H', '--host', type=str, default='127.0.0.1', metavar='',
                            help='Host address e.g. "127.0.0.1"')
        parser.add_argument('-p', '--port', type=int, default=65000, metavar='',
                            help='Port number of Command Channel e.g. "65000"')
        return parser.parse_args()

    @staticmethod
    def send_object_message(s: socket.socket, message: object) -> None:
        """
        Serializes and sends 1 object message.
        Sends header with message length.
        """
        message = pickle.dumps(message)
        message_header = bytes(f'{len(message):<{Server.HEADER_LENGTH}}', 'utf-8')
        s.sendall(message_header + message)

    @staticmethod
    def receive_object_message(s: socket.socket) -> Optional[dict]:
        """
        Receives 1 object message and deserialize it.
        """
        try:
            message_header = s.recv(Server.HEADER_LENGTH)
            if not message_header:
                print('Failed to receive message header!')
                return None

            message_length = int(message_header.decode('utf-8').strip())
            message = s.recv(message_length)
            if not message:
                print('Failed to receive message!')
                return None

            message = pickle.loads(message)
            return message

        except Exception as e:
            print(f'Exception occurred during receiving a message!\n{e}')
            return None

    def run(self) -> None:
        """
        Main loop of server. Server listens for connections and handles each in separate thread.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind((self.host, self.port))
            server.listen(5)
            # TODO: tls wrapper
            print(f'Server listening on {self.host}:{self.port}')

            while True:
                conn, address = server.accept()
                print(f'Connection from {address}')
                t = threading.Thread(target=self.handle_connection, args=(conn, address))
                t.start()

    def handle_connection(self, conn: socket.socket, address: Tuple[str, int]) -> None:
        """
        Handles connection with individual client, manages Command Channel, starts thread handling Data Channel.
        """
        # Authenticate user
        if not Server.authenticate_user(conn):
            print(f'User authentication from {address} failed!')
            print(f'Connection with {address} closed')
            conn.close()
            return

        print(f'User authentication from {address} successful!')

        # Agree on Data Channel
        data_conn = self.agree_on_data_channel(conn, address)
        if not data_conn:
            print(f'Failed to establish Data Channel connection with {address}')
            print(f'Connection with {address} closed')
            conn.close()
            return

        print(f'Data channel established with {address}')

        # Start Data Channel thread
        dt = threading.Thread(target=self.handle_data_channel, args=(data_conn,))
        dt.start()

        # Listen for new commands from user, verify and respond to them
        self.handle_commands(conn, address)

    @staticmethod
    def authenticate_user(conn: socket.socket) -> bool:
        """
        Handles user authentication by comparing hash received from user with hashes stored in authentication file.
        """
        user_credentials = Server.receive_object_message(conn)
        if not user_credentials:
            return False

        try:
            with open('auth.json', 'r', encoding='utf-8') as f:
                auth_data = json.load(f)

            # Compare hashes
            if auth_data[user_credentials['name'].decode('utf-8')] == user_credentials['pass']:
                # Send "OK" status
                Server.send_object_message(conn, {'status': 'OK'})
                return True

            Server.send_object_message(conn, {'status': 'INV'})  # Invalid credentials
            return False

        except Exception as e:
            print(f'Exception occurred during user authentication!\n{e}')
            return False

    def agree_on_data_channel(self, conn: socket.socket, address: Tuple[str, int]) -> Optional[socket.socket]:
        """
        Negotiates Data Channel.
        """
        Server.send_object_message(conn, {'mode': 'ready'})
        connection_mode_message = Server.receive_object_message(conn)
        try:
            if connection_mode_message['mode'] == 'p':
                return self.connect_data_channel_passive(conn)
            elif connection_mode_message['mode'] == 'a':
                return self.connect_data_channel_active(conn)
            else:
                raise Exception('Client sent invalid Data Channel connection mode argument!')

        except Exception as e:
            print(f'Exception occurred during attempt to establish Data Channel connection with {address}\n{e}')
            return None

    def connect_data_channel_passive(self, conn: socket.socket) -> socket.socket:
        """
        Performs connection with server Data Channel in passive mode.
        """
        # Create Data Channel and send port number to client
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as data_channel:
            data_channel.bind((self.host, 0))  # Get random unused port
            data_channel.listen()

            port = int(data_channel.getsockname()[1])
            Server.send_object_message(conn, {'port': port})

            connected = False

            while not connected:
                data_conn, address = data_channel.accept()
                connected = True

            return data_conn

    def connect_data_channel_active(self, s: socket.socket) -> socket.socket:
        """
        Performs connection with server Data Channel in active mode.
        """
        pass

    def handle_commands(self, conn: socket.socket, address: Tuple[str, int]) -> None:
        """
        Receives commands from client, verifies and responds to them.
        """
        pass

    def handle_data_channel(self, data_conn: socket.socket):
        """
        Handles Data Channel - sending and receiving files.
        """
        pass


def main() -> None:
    server = Server()
    server.run()


if __name__ == '__main__':
    main()
