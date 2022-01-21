import argparse
import cmd
import hashlib
import os
import pickle
import platform
import queue
import random
import socket
import ssl
import threading
from types import SimpleNamespace
from typing import Optional

from file_tree_maker import FileTreeMaker


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

        # Thread-safe buffer for communicating between threads
        # responsible for handling user input and sending commands
        self.command_buffer = queue.Queue()
        # Responsible for communication between Data Channel and Command Channel
        self.command_data_communication_buffer = queue.Queue()

        self.command_thread_event = threading.Event()
        self.input_thread_event = threading.Event()
        self.data_thread_event = threading.Event()
        self.exit = False

        self.input_handler = None
        self.is_text_mode = False

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

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations('cert.pem')

        # Establish connection with command channel
        try:
            sock = socket.create_connection((self.server_host, self.server_port))
        except socket.error as e:
            print(f'Connection failed!\n{e}')
            quit(1)

        with context.wrap_socket(sock, server_side=False, server_hostname="projekt.psi") as s:
            s.settimeout(5)

            # Authenticate user
            if not Client.authenticate_user(s):
                print('Authentication failed!')
                quit(1)

            # Successful authentication - agree on Data Channel
            data_s = self.agree_on_data_channel(s)
            if not data_s:
                print('Could not agree on Data Channel!')
                quit(1)

            print(f'Connection successful using {s.version()}')

            # Start Data Channel Thread
            td = threading.Thread(target=self.handle_data_channel, args=(data_s,))
            td.start()

            # Start Command Thread
            t = threading.Thread(target=self.handle_commands, args=(s,))
            t.start()

            # Listen for user commands
            self.handle_user_input()

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
            return Client.connect_data_channel_active(s)

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
            data_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_s.settimeout(5)
            data_s.connect((self.server_host, port_number))

            return data_s

        except Exception as e:
            print(f'Exception occurred during attempt to establish connection with Data Channel in passive mode!\n{e}')
            return None

    @staticmethod
    def connect_data_channel_active(s: socket.socket) -> Optional[socket.socket]:
        """
        Performs connection with server Data Channel in active mode.
        """
        try:
            message = Client.receive_object_message(s)
            if not message['mode'] == 'ready':
                return None

            Client.send_object_message(s, {'mode': 'a'})

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as data_channel:
                data_channel.bind((s.getsockname()[0], 0))  # Get random unused port
                data_channel.listen(1)

                port = int(data_channel.getsockname()[1])
                Client.send_object_message(s, {'port': port})

                connected = False

                while not connected:
                    data_conn, address = data_channel.accept()
                    connected = True

            return data_conn

        except Exception as e:
            print(f'Exception occurred during attempt to establish connection with Data Channel in active mode!\n{e}')
            return None

    def handle_user_input(self) -> None:
        """
        Receives user commands from console, validates and put them in command buffer.
        """

        client = self

        # Wait for user input and validate it
        class HandleInput(cmd.Cmd):
            prompt = ''
            intro = 'Welcome to simple FTP!'

            def __init__(self):
                super().__init__()
                self.current_local_dir = os.getcwd()
                self.current_dir = ''

                self.show_local = True

                self.emergency_exit = False

            def preloop(self) -> None:
                """
                Runs before the start of input loop.
                """
                HandleInput.prompt = f'(local) {self.current_local_dir}> '

            def do_cld(self, *args) -> None:
                """
                Change current local directory.
                Syntax:
                cld <dir/path_to_dir>
                """
                try:
                    path = args[0]
                    os.chdir(path)
                    self.current_local_dir = os.getcwd()
                    if self.show_local:
                        HandleInput.prompt = f'(local) {self.current_local_dir}> '
                except OSError:
                    print('*** Invalid path to directory or directory name.')

            def do_cd(self, args) -> None:
                """
                Change remote working directory.
                Syntax:
                cd <dir/path_to_dir>
                """
                args = args.split()
                # Add command to command buffer and wait for response
                try:
                    path = args[0]
                    client.command_buffer.put({'cd': path})
                    client.command_thread_event.set()  # Inform command thread
                    client.input_thread_event.wait()  # Wait for command thread response
                    client.input_thread_event.clear()  # Clear your own flag
                    command = client.command_buffer.get()
                    if 'cd' in command.keys() and command['cd'] != 'ERR':
                        self.current_dir = command['cd']
                        if not self.show_local:
                            HandleInput.prompt = f'(remote) {self.current_dir}> '
                    elif 'ERR' in command.keys():
                        self.do_exit(args)
                    else:
                        print('*** Invalid path to directory or directory name.')
                except Exception as e:
                    print(f'Exception occurred during handling "cd" command\n{e}')

            def do_get(self, args) -> None:
                """
                Downloads file from specified path. Default mode = binary.
                Syntax:
                get <path> <mode>
                mode = -b | -t
                """
                args = args.split()
                client.is_text_mode = False
                try:
                    for arg in args:
                        if arg == '-t' or arg == '-T':
                            client.is_text_mode = True

                    i = 0
                    while i < len(args) and len(args[i]) and args[i][0] == '-':
                        i += 1
                    if i == len(args):
                        print('*** No file specified')
                        return
                    path = args[i]

                    # Add command to command buffer and wait for response
                    client.command_buffer.put({'get': path})
                    client.command_thread_event.set()
                    client.input_thread_event.wait()  # Wait for command thread response
                    client.input_thread_event.clear()
                    command = client.command_buffer.get()
                    if 'get' in command.keys() and command['get'] != 'ERR':
                        print('Downloading...')
                    elif 'ERR' in command.keys():  # No connection
                        self.emergency_exit = True
                        print('Closing app...')
                    else:
                        print('*** Invalid file path.')
                except Exception as e:
                    print(f'Exception occurred during handling "get" command\n{e}')

            def do_put(self, args) -> None:
                """
                Uploads file from specified path to current remote directory. Default mode = binary.
                Syntax:
                put <path> <mode>
                mode = -b | -t
                """
                try:
                    args = args.split()
                    path = args[0]
                    # Check if specified file exists
                    if not os.path.isfile(path):
                        print('*** Invalid file path.')
                        return
                    # Add command to command buffer and wait for response
                    client.command_buffer.put({'put': path})
                    client.command_thread_event.set()
                    client.input_thread_event.wait()  # Wait for command thread response
                    client.input_thread_event.clear()
                    command = client.command_buffer.get()
                    if 'put' in command.keys() and command['put'] != 'ERR':
                        print('Uploading...')
                    elif 'ERR' in command.keys():  # No connection
                        self.emergency_exit = True
                        print('Closing app...')
                    else:
                        print('*** Invalid file path.')

                except Exception as e:
                    print(f'Exception occurred during handling "put" command\n{e}')

            def do_fl(self, args) -> None:
                """
                Flip prompt from local to remote or vice versa.
                """
                self.show_local = not self.show_local
                if self.show_local:
                    HandleInput.prompt = f'(local) {self.current_local_dir}> '
                else:
                    # If it's unknown
                    if self.current_dir == '':
                        self.do_cd('.')
                    HandleInput.prompt = f'(remote) {self.current_dir}> '

            def do_lls(self, args) -> None:
                """
                List local files and directories.
                Syntax:
                lls <root> <recursion_level>
                - root: default = '.'
                - recursion_level: default = '1' (prints all from current directory);
                                   if equals to -1 - prints all levels
                """
                args = args.split()
                try:
                    # Default - print all from current directory
                    if len(args) == 0:
                        namespace = SimpleNamespace(root='.', output='', exclude_folder=[],
                                                    exclude_name=[], max_level=1)
                        print(FileTreeMaker().make(namespace))

                    # Print all from given directory
                    elif len(args) == 1:
                        namespace = SimpleNamespace(root=args[0], output='', exclude_folder=[],
                                                    exclude_name=[], max_level=1)
                        print(FileTreeMaker().make(namespace))

                    # Print from specified directory recursively
                    elif len(args) == 2:
                        namespace = SimpleNamespace(root=args[0], output='', exclude_folder=[],
                                                    exclude_name=[], max_level=int(args[1]))
                        print(FileTreeMaker().make(namespace))

                    else:
                        raise Exception

                except Exception:
                    print('*** Invalid arguments for command "lls".')

            def do_ls(self, args) -> None:
                """
                List remote files and directories.
                Syntax:
                lls <root> <recursion_level>
                - root: default = '.'
                - recursion_level: default = '1' (prints all from current directory);
                                   if equals to -1 - prints all levels
                """
                # Add command to command buffer and wait for response
                try:
                    client.command_buffer.put({'ls': args})
                    client.command_thread_event.set()
                    client.input_thread_event.wait()  # Wait for command thread response
                    client.input_thread_event.clear()
                    command = client.command_buffer.get()
                    if 'ls' in command.keys() and command['ls'] != 'ERR':
                        print(command['ls'])
                    elif 'ERR' in command.keys():
                        self.do_exit(args)
                    else:
                        print('*** Invalid arguments for command "ls".')
                except Exception as e:
                    print(f'Exception occurred during handling "ls" command\n{e}')

            def do_exit(self, args) -> bool:
                """
                Exit the application.
                """
                # Add command to command buffer and wait for response
                try:
                    client.command_buffer.put({'exit': ''})
                    client.command_thread_event.set()
                    self.emergency_exit = True
                    print('Closing app...')
                    return True
                except Exception:
                    print('*** Invalid arguments for command "exit".')

            def postcmd(self, stop: bool, line: str) -> bool:
                """
                Runs after each execution of input function. Checks for emergency_exit flag.
                If flag is set, then input loop will be closed.
                """
                return self.emergency_exit

        client.input_handler = HandleInput()
        client.input_handler.cmdloop()

    def handle_commands(self, s: socket.socket):
        """
        Handles user commands and responses from server.
        """
        while not self.exit:
            self.command_thread_event.wait()  # Wait for command
            self.command_thread_event.clear()  # Reset flag
            command = self.command_buffer.get()

            if 'cd' in command.keys() or 'ls' in command.keys():
                try:
                    self.send_object_message(s, command)
                    message = self.receive_object_message(s)
                    self.command_buffer.put(message)
                    self.input_thread_event.set()
                except Exception as e:
                    print(f'Exception occurred in Command Channel while handling "cd" or "ls" command\n{e}')
                    self.exit = True
                    self.command_buffer.put({'ERR': ''})
                    self.input_thread_event.set()

            elif 'get' in command.keys():
                try:
                    new_filename = ''
                    # Check if file with specific name exists locally
                    if os.path.isfile(os.path.join(os.getcwd(), command['get'])):
                        print('File with such path already exists on local machine')
                        # Add random extension to filename in such case
                        path, filename = os.path.split(command['get'])
                        filename, file_type = os.path.splitext(filename)
                        extension = ''.join([str(random.randint(0, 9)) for _ in range(10)])
                        new_filename = f'{filename}_{extension}{file_type}'
                        print(f'File will be saved as: {new_filename}')

                    self.send_object_message(s, command)
                    message = self.receive_object_message(s)
                    self.command_buffer.put(message)
                    self.input_thread_event.set()
                    if message['get'] == 'OK':
                        # Initialize download
                        self.command_data_communication_buffer.put({'get': [command['get'], new_filename]})
                        self.data_thread_event.set()
                        self.command_thread_event.wait()
                        self.command_thread_event.clear()
                        self.send_object_message(s, {'get': 'ready'})
                except Exception as e:
                    print(f'Exception occurred in Command Channel while handling "get" command\n{e}')
                    self.exit = True
                    self.command_buffer.put({'ERR': ''})
                    self.input_thread_event.set()

            elif 'put' in command.keys():
                try:
                    self.send_object_message(s, command)
                    message = self.receive_object_message(s)
                    if message['put'][0] == 'OK':
                        if message['put'][1] != '':
                            print(message['put'][1])

                        self.command_buffer.put({'put': 'OK'})
                        self.input_thread_event.set()

                        self.command_data_communication_buffer.put(command)
                        message = self.receive_object_message(s)
                        if message['put'] == 'ready':
                            # Inform Data Channel
                            self.data_thread_event.set()

                except Exception as e:
                    print(f'Exception occurred in Command Channel while handling "put" command\n{e}')
                    self.exit = True
                    self.command_buffer.put({'ERR': ''})
                    self.input_thread_event.set()

            elif 'exit' in command.keys():
                # First close Data Channel
                self.exit = True
                self.data_thread_event.set()
                self.command_thread_event.wait()  # Sleep until Data Channel is not closed
                self.command_thread_event.clear()  # Reset flag

                # Then close Command Channel
                s.close()
                print('Command Channel closed.')

                # Finally, quit the app
                quit(0)

            else:
                print(f'*** Received invalid command: {command}')

        # Exit app
        self.data_thread_event.set()
        self.command_thread_event.wait()  # Sleep until Data Channel is not closed
        self.command_thread_event.clear()  # Reset flag
        s.close()
        print('Command Channel closed.')
        quit(0)

    def handle_data_channel(self, data_s: socket.socket) -> None:
        """
        Handles data transfer between user and server
        """
        while True:
            self.data_thread_event.wait()
            self.data_thread_event.clear()
            if self.exit:
                # App is about to shut down - disconnect
                data_s.close()
                self.command_thread_event.set()
                print('Data Channel closed.')
                break

            command = self.command_data_communication_buffer.get()
            if 'get' in command.keys():
                f_name = command['get'][0] if command['get'][1] == '' else command['get'][1]
                with open(f_name, 'wb') as f:
                    self.command_thread_event.set()  # Inform Command Channel about readiness
                    try:
                        data_header = data_s.recv(Client.HEADER_LENGTH)
                        if not data_header:
                            print('Failed to receive data header!')
                            break

                        data_length = int(data_header.decode('utf-8').strip())
                        data = data_s.recv(data_length)

                        if not data:
                            print('Failed to receive data!')
                            break

                        if self.is_text_mode:
                            data = data.replace(b"/n/r", b"/n")
                            if platform.system() == "Windows":
                                data = data.replace(b"/n", b"/n/r")
                            elif platform.system() != "Linux":
                                print(f'detected an unsupported system: {platform.system()}, '
                                      f'assuming Linux-like behavior')

                        f.write(data)

                    except Exception as e:
                        print(f'Exception occurred during receiving data!\n{e}')
                        return None

            elif 'put' in command.keys():
                with open(command['put'], 'rb') as f:

                    data = f.read()
                    filesize = len(data)
                    data_header = bytes(f'{filesize:<{Client.HEADER_LENGTH}}', 'utf-8')
                    data_s.sendall(data_header + data)


def main() -> None:
    client = Client()
    client.run()


if __name__ == '__main__':
    main()
