import socket
import threading
import argparse
import queue
import time
from typing import Tuple, Optional, List
import pickle
import hashlib
import os
import cmd
from types import SimpleNamespace
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

        # Thread-safe buffer for communicating between threads responsible for handling user input and sending commands
        self.command_buffer = queue.Queue()

        self.command_thread_event = threading.Event()
        self.input_thread_event = threading.Event()
        self.exit = False

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
        """
        Handles data transfer between user and server
        """
        while not self.exit:
            pass

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

            def preloop(self) -> None:
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
                    client.command_thread_event.set()
                    client.command_thread_event.clear()
                    client.input_thread_event.wait()  # Wait for command thread response
                    command = client.command_buffer.get()
                    if 'cd' in command.keys() and command['cd'] != 'ERR':
                        self.current_dir = command['cd']
                    else:
                        raise Exception
                except Exception:
                    print('*** Invalid path to directory or directory name.')

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

            def do_lls(self, args):
                """
                List local files and directories.
                Syntax:
                lls <root> <recursion_level>
                - root: default = '.'
                - recursion_level: default = '1' (prints all from current directory);
                                   if equals to -1 - prints all levels
                """
                args = args.split()
                print(args)
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

        HandleInput().cmdloop()

    def handle_commands(self, s: socket.socket):
        """
        Handles user commands and responses from server.
        """
        while not self.exit:
            self.command_thread_event.wait()  # Wait for command
            command = self.command_buffer.get()

            if 'cd' in command.keys():
                pass

            elif 'ls' in command.keys():
                pass

            elif 'get' in command.keys():
                pass

            elif 'put' in command.keys():
                pass

            elif 'exit' in command.keys():
                pass

            else:
                pass




def main() -> None:
    client = Client()
    client.run()


if __name__ == '__main__':
    main()
