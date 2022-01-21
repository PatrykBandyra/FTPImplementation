import socket
import ssl
import threading
import argparse
import queue
from typing import Tuple, Optional
import pickle
import platform
import json
import os
import random
from types import SimpleNamespace
from file_tree_maker import FileTreeMaker
from Crypto.Cipher import AES
import string
import secrets
import base64


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
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain('cert.pem', 'key.pem')

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.bind((self.host, self.port))
            server_sock.listen(5)

            with context.wrap_socket(server_sock, server_side=True) as server:
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
        data_conn, key, iv = self.agree_on_data_channel(conn, address)
        if not data_conn:
            print(f'Failed to establish Data Channel connection with {address}')
            print(f'Connection with {address} closed')
            conn.close()
            return

        print(f'Data channel established with {address} on port {data_conn.getsockname()[1]}')

        communication_buffer = queue.Queue()
        data_channel_event = threading.Event()
        command_channel_event = threading.Event()

        # Start Data Channel thread
        dt = threading.Thread(target=self.handle_data_channel, args=(data_conn, communication_buffer,
                                                                     data_channel_event, command_channel_event,
                                                                     key, iv))
        dt.start()

        # Listen for new commands from user, verify and respond to them
        self.handle_commands(conn, address, communication_buffer, data_channel_event, command_channel_event)

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

    def agree_on_data_channel(self, conn: socket.socket, address: Tuple[str, int]) -> \
            Optional[Tuple[socket.socket, bytes, bytes]]:
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

    def connect_data_channel_passive(self, conn: socket.socket) -> Tuple[socket.socket, bytes, bytes]:
        """
        Performs connection with server Data Channel in passive mode.
        """
        # Create Data Channel and send port number to client
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as data_channel:
            data_channel.bind((self.host, 0))  # Get random unused port
            data_channel.listen(1)

            port = int(data_channel.getsockname()[1])
            Server.send_object_message(conn, {'port': port})

            key = ''.join(secrets.choice(string.ascii_letters + string.digits) for x in range(32))
            key = key.encode("utf8")
            Server.send_object_message(conn, key)

            iv = ''.join(secrets.choice(string.ascii_letters + string.digits) for x in range(16))
            iv = iv.encode("utf8")
            Server.send_object_message(conn, iv)

            connected = False

            while not connected:
                data_conn, address = data_channel.accept()
                connected = True

            return data_conn, key, iv

    def connect_data_channel_active(self, s: socket.socket) -> Optional[Tuple[socket.socket, dict, dict]]:
        """
        Performs connection with server Data Channel in active mode.
        """
        try:
            message = Server.receive_object_message(s)

            if not message['port']:
                return None

            key_message = Server.receive_object_message(s)
            key = key_message

            iv_message = Server.receive_object_message(s)
            iv = iv_message

            # Connect to a port specified by client
            data_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_s.settimeout(5)
            data_s.connect((s.getsockname()[0], message['port']))

            return data_s, key, iv

        except Exception as e:
            print(f'Exception occurred during attempt to establish connection with Data Channel in active mode!\n{e}')
            return None

    def handle_commands(self, conn: socket.socket, address: Tuple[str, int], communication_buffer: queue.Queue,
                        data_channel_event: threading.Event, command_channel_event: threading.Event) -> None:
        """
        Receives commands from client, verifies and responds to them.
        """
        current_dir = os.getcwd()  # Only to init
        while True:
            command = self.receive_object_message(conn)

            if not command:
                conn.close()
                print(f'Connection with {address} closed!')
                communication_buffer.put({'close': ''})  # Make Data Channel close its connection
                data_channel_event.set()
                break

            try:
                if 'cd' in command.keys():
                    # Change current working directory if path is valid
                    try:
                        # Go up in directory tree
                        if command['cd'].strip() == '..':
                            current_dir = os.path.dirname(current_dir)

                        # Return current directory
                        elif command['cd'].strip() == '.':
                            pass

                        # Go down directory tree or change absolute path
                        elif os.path.isdir(os.path.join(current_dir, command['cd'])):
                            if os.path.isabs(command['cd']):
                                current_dir = command['cd']
                            else:
                                current_dir = os.path.join(current_dir, command['cd'])

                        else:
                            raise Exception('Invalid command!')

                        self.send_object_message(conn, {'cd': current_dir})  # Send to client updated path

                    except Exception as e:
                        print(f'Exception occurred in command channel of {address}\n{e}')
                        self.send_object_message(conn, {'cd': 'ERR'})

                elif 'ls' in command.keys():

                    try:
                        args = command['ls'].split()

                        # Default - print all from current directory
                        if len(args) == 0:
                            namespace = SimpleNamespace(root=current_dir, output='', exclude_folder=[],
                                                        exclude_name=[], max_level=1)
                            tree_str = FileTreeMaker().make(namespace)

                        # Print all from given directory
                        elif len(args) == 1:
                            r = args[0].strip()
                            if r == '.':
                                r = current_dir
                            namespace = SimpleNamespace(root=r, output='', exclude_folder=[],
                                                        exclude_name=[], max_level=1)
                            tree_str = FileTreeMaker().make(namespace)

                        # Print from specified directory recursively
                        elif len(args) == 2:
                            r = args[0].strip()
                            if r == '.':
                                r = current_dir
                            namespace = SimpleNamespace(root=r, output='', exclude_folder=[],
                                                        exclude_name=[], max_level=int(args[1]))
                            tree_str = FileTreeMaker().make(namespace)

                        else:
                            raise Exception

                        self.send_object_message(conn, {'ls': tree_str})

                    except Exception as e:
                        print(f'Exception occurred in command channel of {address}\n{e}')
                        self.send_object_message(conn, {'ls': 'ERR'})

                elif 'get' in command.keys():
                    try:
                        # Validate path of received file
                        filepath = command['get']

                        if os.path.isfile(os.path.join(current_dir, filepath)):
                            if not os.path.isabs(filepath):
                                filepath = os.path.join(current_dir, filepath)

                            # Init upload
                            communication_buffer.put({'get': filepath})
                            self.send_object_message(conn, {'get': 'OK'})
                            message = self.receive_object_message(conn)  # Wait for response message
                            if message['get'] == 'ready':
                                data_channel_event.set()

                        else:
                            self.send_object_message(conn, {'get': 'ERR'})

                    except Exception as e:
                        print(f'Exception occurred in command channel of {address}\n{e}')
                        self.send_object_message(conn, {'get': 'ERR'})

                elif 'put' in command.keys():
                    try:
                        # Create remote filepath from local filepath
                        filepath = command['put']  # Local filepath
                        _, filename = os.path.split(filepath)
                        filepath = os.path.join(current_dir, filename)  # Filepath for file to be uploaded to
                        is_text_mode = command["is_text_mode"]

                        # Check if generated filepath already exists
                        info = ''
                        if os.path.isfile(filepath):
                            # Add random extension to filename in such case
                            path, filename = os.path.split(filepath)
                            filename, file_type = os.path.splitext(filename)
                            extension = ''.join([str(random.randint(0, 9)) for _ in range(10)])
                            new_filename = f'{filename}_{extension}{file_type}'
                            filepath = os.path.join(current_dir, new_filename)

                            info = f'File with such name already exists on server. ' \
                                   f'File will be uploaded as: {new_filename}'

                        # Init download (from client to server)
                        communication_buffer.put({'put': filepath, 'is_text_mode': is_text_mode})
                        self.send_object_message(conn, {'put': ['OK', info]})
                        data_channel_event.set()
                        command_channel_event.wait()  # Wait for Data Channel info
                        command_channel_event.clear()
                        self.send_object_message(conn, {'put': 'ready'})

                    except Exception as e:
                        print(f'Exception occurred in command channel of {address}\n{e}')
                        self.send_object_message(conn, {'put': 'ERR'})

                else:
                    print(f'Received invalid command from {address}')

            except Exception as e:
                print(f'Exception occurred in command channel of {address}\n{e}')
                try:
                    self.send_object_message(conn, {'ERR': e})
                except Exception as e:
                    print(f'Exception occurred in command channel of {address}\n{e}')

    def handle_data_channel(self, data_conn: socket.socket, communication_buffer: queue.Queue,
                            data_channel_event: threading.Event, command_channel_event: threading.Event,
                            key: bytes, iv: bytes) -> None:
        """
        Handles Data Channel - sending and receiving files.
        """
        while True:
            data_channel_event.wait()  # Wait for task
            data_channel_event.clear()

            command = communication_buffer.get()

            if 'close' in command.keys():
                print(f'Data Channel with {data_conn.getsockname()} closed.')
                data_conn.close()
                break

            elif 'get' in command.keys():
                with open(command['get'], 'rb') as f:

                    data = f.read()
                    data = Server.encrypt(data, key, iv)

                    filesize = len(data)
                    data_header = bytes(f'{filesize:<{Server.HEADER_LENGTH}}', 'utf-8')

                    data_conn.sendall(data_header + data)

            elif 'put' in command.keys():
                with open(command['put'], 'wb') as f:
                    command_channel_event.set()  # Inform about readiness to download a file

                    try:
                        data_header = data_conn.recv(Server.HEADER_LENGTH)
                        if not data_header:
                            print(f'Failed to receive data header! Connection: {data_conn.getsockname()}')
                            break

                        data_length = int(data_header.decode('utf-8').strip())
                        data = data_conn.recv(data_length)

                        if not data:
                            print(f'Failed to receive data! Connection: {data_conn.getsockname()}')
                            break

                        data = Server.decrypt(data, key, iv)

                        if command['is_text_mode']:
                            data = data.replace(b"/n/r", b"/n")
                            if platform.system() == "Windows":
                                data = data.replace(b"/n", b"/n/r")
                            elif platform.system() != "Linux":
                                print(f'detected an unsupported system: {platform.system()}, '
                                      f'assuming Linux-like behavior')

                        f.write(data)

                    except Exception as e:
                        print(f'Exception occurred during receiving data! Connection: {data_conn.getsockname()}\n{e}')
                        return None

    @staticmethod
    def decrypt(message, key, iv):
        """
        Decrypts received message
        """
        message = base64.b64decode(message)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_text = cipher.decrypt(message)
        return decrypted_text[:-ord(decrypted_text[len(decrypted_text) - 1:])]

    @staticmethod
    def encrypt(message, key, iv):
        """
        Encrypts passed message that is going to be sent
        """
        message = message + (AES.block_size - len(message) % AES.block_size) * str.encode(
            chr(AES.block_size - len(message) % AES.block_size))
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted_text = cipher.encrypt(message)
        return base64.b64encode(encrypted_text)


def main() -> None:
    server = Server()
    server.run()


if __name__ == '__main__':
    main()
