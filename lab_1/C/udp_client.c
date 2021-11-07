#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <stdio.h>

#define HOST        "127.0.0.1"
#define PORT        65000
#define BUF_SIZE    512
#define MESSAGE     "Hello darkness, my old friend..."
#define MESSAGE_NUM 10

int main(int argc, char *argv) {
    int sock;
    struct sockaddr_in server;
    char buf[BUF_SIZE];

    /* Create socket. */
    sock = socket(AF_INET, SOCK_DGRAM, 0 );
    if (sock == -1) {
        perror("Opening stream socket");
        exit(1);
    }

    server.sin_family = AF_INET;
    server.sin_port = htons(PORT);
    server.sin_addr.s_addr = inet_addr(HOST);

    for (int i = 1; i <= 10; i++) {
        if (sendto(sock, MESSAGE, sizeof MESSAGE ,0, (struct sockaddr *) &server,sizeof server) == -1)
            perror("sending datagram message");
        printf("Message %d sent\n", i);
    }
    close(sock);
    printf("Client closed\n");
    exit(0);
}
