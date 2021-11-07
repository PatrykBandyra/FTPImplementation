import socket


HOST = '127.0.0.1'
PORT = 65000
BUF_SIZE = 32


if __name__ == '__main__':
    print(f'Will listen on {HOST}:{PORT}')

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(5)

        while True:
            conn, address = s.accept()
            with conn:
                print(f'Connected from: {address}')
                while True:
                    data = conn.recv(BUF_SIZE)
                    if not data:
                        break
                    print(f'Message from client {address}: {str(data.decode("ascii"))}')

            conn.close()
            print('Connection closed by client')
