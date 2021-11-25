#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>

#define HOST        "127.0.0.1"
#define PORT        65000
#define BUF_SIZE    1024

int main(int argc, char *argv) {
    int sock;
    struct sockaddr_in server;
    char msg[BUF_SIZE];
    
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock == -1) {
        perror("Opening stream socket");
        exit(1);
    }

    server.sin_family = AF_INET;
    server.sin_port = htons(PORT);
    server.sin_addr.s_addr = inet_addr(HOST);

    if (connect(sock, (struct sockaddr *) &server, sizeof server)== -1) {
        perror("connecting stream socket");
        exit(1);
    }

    for (int i = 1; ; i++) {
        if (sendto(sock, msg, sizeof(msg), 0, (struct sockaddr *) &server, sizeof server) == -1)
            perror("sending stream message");
        printf("Message %d sent\n", i);
        fflush(stdout);
    }
    close(sock);
    printf("Client closed\n");
    exit(0);
}
