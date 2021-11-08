import socket


HOST = '127.0.0.1'
PORT = 65000
MESSAGE = 'Hello darkness, my old friend...'
MESSAGE_NUM = 10


if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        message = MESSAGE.encode('ascii')
        for i in range(MESSAGE_NUM):
            s.sendto(message, (HOST, PORT))
            print(f'Message {i+1} sent')
    print('Client closed')
