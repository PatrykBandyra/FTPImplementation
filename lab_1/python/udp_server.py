import socket


HOST = '127.0.0.1'
PORT = 65000
BUF_SIZE = 512


if __name__ == '__main__':
    print(f'Will listen on {HOST}:{PORT}')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((HOST, PORT))
        while True:
            data, address = s.recvfrom(BUF_SIZE)
            print(f'Message from client {address}: {str(data.decode("ascii"))}')
            if not data:
                print('Error in datagram')
                break
