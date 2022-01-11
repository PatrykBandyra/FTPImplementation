import socket
import threading
import argparse
import queue
import time
from typing import Tuple, Optional
import pickle
import hashlib


class Client:
    """
    Multithread tcp client of simple FTP.
    """

    HEADER_LENGTH = 10

    def __init__(self):
        args = Client.get_args()
        self.server_host = args.host
        self.server_port = args.port
        self.mode = args.mode

        # Thread-safe buffer for communicating between threads responsible for handling user input and sending commands
        self.command_buffer = queue.Queue()

        # Thread events
        self.credentials_entered = threading.Event()
        self.authenticated = threading.Event()

    @staticmethod
    def get_args() -> argparse.Namespace:
        parser = argparse.ArgumentParser(description='Run simple FTP client.')
        parser.add_argument('-H', '--host', type=str, default='127.0.0.1', metavar='',
                            help='Address of server e.g. "127.0.0.1"')
        parser.add_argument('-p', '--port', type=int, default=65000, metavar='',
                            help='Port number of server Command Channel e.g. "65000"')
        parser.add_argument('-m', '--mode', type=str, default='p', choices=['a', 'p'], metavar='',
                            help='Mode of establishing connection with server')
        return parser.parse_args()

    @staticmethod
    def send_object_message(s: socket.socket, message: object) -> None:
        """
        Serializes and sends 1 object message.
        Sends header with message length.
        """
        message = pickle.dumps(message)
        message_header = bytes(f'{len(message):<{Client.HEADER_LENGTH}}', 'utf-8')
        s.sendall(message_header + message)

    @staticmethod
    def receive_object_message(s: socket.socket) -> Optional[dict]:
        """
        Receives 1 object message and deserialize it.
        """
        try:
            message_header = s.recv(Client.HEADER_LENGTH)
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

        # TODO: tls wrapper
        # Establish connection with command channel
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            try:
                s.connect((self.server_host, self.server_port))
            except socket.error as e:
                print(f'Connection failed!\n{e}')

            # Authenticate user
            if not Client.authenticate_user(s):
                print('Authentication failed!')
                quit(1)

            # Successful authentication - agree on Data Channel
            data_s = self.agree_on_data_channel(s)
            if not data_s:
                print('Could not agree on Data Channel!')
                quit(1)

            # Start Data Channel Thread
            td = threading.Thread(target=self.handle_data_channel, args=(data_s,))
            td.start()

            # Start Console Input Thread
            t = threading.Thread(target=self.handle_user_input)
            t.start()

            # Listen for new commands from user, verify and send them
            self.handle_commands()

    @staticmethod
    def authenticate_user(s: socket.socket) -> bool:
        """
        Handles authentication of user with server.
        """
        username = input('Insert username: ').encode('utf-8')
        password = input('Insert password: ').encode('utf-8')

        hasher = hashlib.sha512()
        hasher.update(password)
        hashed_pass = hasher.hexdigest()

        user_credentials = {'name': username, 'pass': hashed_pass}
        Client.send_object_message(s, user_credentials)

        status_message = Client.receive_object_message(s)
        try:
            if status_message['status'] == 'OK':
                return True
            return False

        except Exception as e:
            print(f'Exception occurred during authentication!\n{e}')
            return False

    def agree_on_data_channel(self, s: socket.socket) -> Optional[socket.socket]:
        """
        Negotiates Data Channel
        """
        if self.mode == 'p':
            return self.connect_data_channel_passive(s)
        else:
            return self.connect_data_channel_active(s)

    def connect_data_channel_passive(self, s: socket.socket) -> Optional[socket.socket]:
        """
        Performs connection with server Data Channel in passive mode.
        """
        # Wait for server message to choose Data Channel connection mode
        try:
            message = Client.receive_object_message(s)
            if not message['mode'] == 'ready':
                return None

            Client.send_object_message(s, {'mode': 'p'})
            port_number_message = Client.receive_object_message(s)
            port_number = int(port_number_message['port'])

            # Connect to specified server port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as data_s:
                data_s.settimeout(5)
                data_s.connect((self.server_host, port_number))

                return data_s

        except Exception as e:
            print(f'Exception occurred during attempt to establish connection with Data Channel in passive mode!\n{e}')
            return None

    def connect_data_channel_active(self, s: socket.socket):
        """
        Performs connection with server Data Channel in active mode.
        """
        pass

    def handle_data_channel(self, data_s: socket.socket):
        while True:
            print('Data channel')
            time.sleep(3)

    def handle_user_input(self) -> None:
        """
        Receives user commands from console, validates and put them in command buffer.
        """
        pass

    def handle_commands(self):
        """
        Handles user commands and responses from server.
        """
        pass


def main() -> None:
    client = Client()
    client.run()


if __name__ == '__main__':
    main()
