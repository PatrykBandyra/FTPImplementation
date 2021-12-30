import socket
import threading
import argparse
import queue
from typing import Tuple
import pickle


class Server:
    """
    Multithread tcp socket server for managing simple FTP.
    """
    def __init__(self):
        args = Server.get_args()
        self.host = args.host
        self.port = args.port

        # Buffer for storing file paths of files currently being uploaded to the server
        self.files_in_transfer_buffer = queue.Queue()  # Thread-safe

    @staticmethod
    def get_args() -> argparse.Namespace:
        parser = argparse.ArgumentParser(description='Run simple FTP server.')
        parser.add_argument('-H', '--host', type=str, default='127.0.0.1', metavar='',
                            help='Host address e.g. "127.0.0.1"')
        parser.add_argument('-p', '--port', type=int, default=65000, metavar='',
                            help='Port number of Command Channel e.g. "65000"')
        return parser.parse_args()

    def run(self) -> None:
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
        while True:
            data = conn.recv(1024)
            if not data:  # Socket closed
                break
            # Logic
            # 1. Authenticate user
            # 2. Agree on Data Channel
            # 3. Start Data Channel Thread
            # 6. Listen for new commands from user, verify and respond to them

        print(f'Connection with {address} closed')
        conn.close()


def main() -> None:
    server = Server()
    server.run()


if __name__ == '__main__':
    main()
