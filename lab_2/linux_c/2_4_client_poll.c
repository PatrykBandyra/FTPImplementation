#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <poll.h>
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

    struct pollfd p[1];
    p[0].fd = sock;
    p[0].events = POLLOUT;

    if (connect(sock, (struct sockaddr *) &server, sizeof server)== -1) {
        perror("connecting stream socket");
        exit(1);
    }

    for (int i = 1, wait = 0; poll(p, 1, 0) != -1;) {
        if (p[0].revents & POLLOUT) {
            if (sendto(sock, msg, sizeof(msg), 0, (struct sockaddr*)&server, sizeof server) == -1) {
                perror("sending stream message");
            }
            printf("Message %d sent\n", i);
            fflush(stdout);
            i++;
        }
        else if (p[0].revents & (POLLERR | POLLHUP)) {
            break;
        } else {
            if (wait != i) {
                wait = i;
                // zastosowanie zmiennej wait - tylko po to, aby napis wyświetlil sie jednokrotnie, przy rozpoczeciu okresu oczekiwania na mozliwosc wyslania kolejnych wiadomosci
                // w rezultacie napis będzie caly czas "wisial" na wierzchu konsoli, ponieważ klient prawie caly czas czeka
                printf("Now we will check periodically for opportunity to send next messages. Meanwhile something else can be done.");
                fflush(stdout);
            }
        }
    }
    close(sock);
    printf("Client closed\n");
    exit(0);
}
