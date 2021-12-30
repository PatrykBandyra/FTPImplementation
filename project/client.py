import socket
import threading
import argparse
import queue
from typing import Tuple
import pickle


class Client:
    """
    Multithread tcp client of simple FTP.
    """
    def __init__(self):
        args = Client.get_args()
        self.server_host = args.host
        self.server_port = args.port

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

    def run(self) -> None:

        # TODO: tls wrapper
        # 1. Establish connection with command channel
        # 2. Authenticate
        # 3. Agree on Data Channel
        # 4. Start Data Channel Thread
        # 5. Start Console Input Thread
        # 6. Listen for new commands from user, verify and send them
        pass


def main() -> None:
    client = Client()
    client.run()


if __name__ == '__main__':
    main()
