import socket
from struct import *


HOST = '127.0.0.1'
PORT = 65000
BUF_SIZE = 24


def print_formatted_data(data):
    # C Struct format
    # long long int a;
    # int b;
    # short int c;
    # short int d;
    # char e[8];

    numerical_data = unpack('qi2h', data[:-8])
    char_data = data[-8:-1]
    print('Received structure:')
    print(f'a = {numerical_data[0]}')
    print(f'b = {numerical_data[1]}')
    print(f'c = {numerical_data[2]}')
    print(f'd = {numerical_data[3]}')
    print(f'e = {char_data.decode("ascii")}')


if __name__ == '__main__':
    print(f'Will listen on {HOST}:{PORT}')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((HOST, PORT))
        while True:
            data, address = s.recvfrom(BUF_SIZE)
            print(f'Message from client {address}:')
            print_formatted_data(data)

            if not data:
                print('Error in datagram')
                break
