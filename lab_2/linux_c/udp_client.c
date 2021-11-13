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

struct SendMeBabe {
	long long int a;
	int b;
	short int c;
	short int d;
	char e[8];
};  // 24 bytes - no padding between values

int main(int argc, char *argv) {
    int sock;
    struct sockaddr_in server;
	struct SendMeBabe msg = { 12345678910, 333444, 66, 33, "Hello!!"};
	int msgLen = sizeof(msg);

    /* Create socket. */
    sock = socket(AF_INET, SOCK_DGRAM, 0 );
    if (sock == -1) {
        perror("Opening stream socket");
        exit(1);
    }

    server.sin_family = AF_INET;
    server.sin_port = htons(PORT);
    server.sin_addr.s_addr = inet_addr(HOST);

    if (sendto(sock, (char*)&msg, msgLen , 0, (struct sockaddr *) &server,sizeof server) == -1)
        perror("sending datagram message");
    printf("Message sent\n");

    close(sock);
    printf("Client closed\n");
    exit(0);
}