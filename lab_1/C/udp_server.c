#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <stdio.h>
#include <arpa/inet.h>

#define HOST     "127.0.0.1"   
#define PORT     65000
#define BUF_SIZE 512
  
int main(int argc, char **argv) {
    int sock, length, result, cli_len;
    struct sockaddr_in server, client;
    char buf[BUF_SIZE];

    sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock == -1) {
        perror("Opening stream socket");
        exit(1);
    }

    server.sin_family = AF_INET;
    server.sin_port = htons(PORT);
    server.sin_addr.s_addr = inet_addr(HOST);

    if (bind(sock, (struct sockaddr *) &server, sizeof server) == -1) {
        perror("Binding stream socket");
        exit(1);
    }
    
    printf("Will listen on %s:%d\n", HOST, PORT);
    memset(buf, 0, BUF_SIZE);
    while(1) {
        result = recvfrom(sock, buf, BUF_SIZE, 0, (struct sockaddr *) &client, &cli_len);
        if (result == -1) {
            perror("receiving datagram packet");
            exit(2);
        }
        char *cli_addr = inet_ntoa(client.sin_addr);
        printf("Message from client ('%s', %d): %s\n", cli_addr, client.sin_port, buf);
    }
    return 0;
}