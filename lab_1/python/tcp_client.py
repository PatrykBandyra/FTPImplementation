import socket


HOST = '127.0.0.1'
PORT = 65000
MESSAGE = 'Hello darkness, my old friend...'
MESSAGE_NUM = 10


if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        message = MESSAGE.encode('ascii')
        for i in range(MESSAGE_NUM):
            s.sendall(message)
            print(f'Message {i} sent')

    print('Client closed')
