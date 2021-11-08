#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <stdio.h>
#include <arpa/inet.h>

#define HOST     "127.0.0.1"   
#define PORT     65000
#define BUF_SIZE 32
  
int main(int argc, char **argv) {
    int sock, length, msgsock, result, cli_len;
    struct sockaddr_in server, client;
    char buf[BUF_SIZE];

    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock == -1) {
        perror("Opening stream socket");
        exit(1);
    }

    server.sin_family = AF_INET;
    server.sin_port = htons(PORT);
    server.sin_addr.s_addr = inet_addr(HOST);

    if (bind(sock, (struct sockaddr *) &server, sizeof server) == -1) {
        perror("Binding stream socket");
        exit(2);
    }

    listen(sock, 5);
    printf("Will listen on %s:%d\n", HOST, PORT);
    memset(buf, 0, BUF_SIZE);

    do {
        cli_len = sizeof(client);
        msgsock = accept(sock, (struct sockaddr *) &client, &cli_len);

        char *cli_addr = inet_ntoa(client.sin_addr);
        printf("Connected from: ('%s', %d)\n", cli_addr, client.sin_port);

        if (msgsock == -1 ) {
             perror("accept");
             exit(3);
        } else do {
            // memset(buf, 0, BUF_SIZE);
            result = read(msgsock, buf, sizeof(buf));
            if (result == -1) {
                perror("reading stream message");
                exit(4); }
            if (result == 0)
                printf("Connection closed by client\n");
            else {
                buf[BUF_SIZE] = '\0';

                printf("Message from client ('%s', %d): %s\n", cli_addr, client.sin_port, buf);
            }
        } while (result != 0);
    } while(1);
    exit(0);
}