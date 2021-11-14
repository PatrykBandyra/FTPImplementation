#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>

#define HOST     "127.0.0.1"   
#define PORT     65000
#define BUF_SIZE 20
  
int main(int argc, char **argv) {
    int sock, length, msgsock, result, cli_len;
    struct sockaddr_in server, client;
    char buf[BUF_SIZE+1];

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

    do {
        cli_len = sizeof(client);
        msgsock = accept(sock, (struct sockaddr *) &client, &cli_len);

        char *cli_addr = inet_ntoa(client.sin_addr);
        printf("Connected from: ('%s', %d)\n", cli_addr, client.sin_port);

        if (msgsock == -1 ) {
             perror("accept");
             exit(3);
        } else {
            int new=1; // bool
            while(1){
                memset(buf, 0, BUF_SIZE+1);
                result = read(msgsock, buf, BUF_SIZE);
                if (result == -1) {
                    perror("reading stream message");
                    exit(4);
                }
                if (result){
                    int to_print=0;
                    for(int i=0; ; i=to_print+1){
                        to_print=strlen(&buf[i]);
                        
                        if(to_print){
                            if(new){
                                printf("Message from client ('%s', %d): %s", cli_addr, client.sin_port, &buf[i]);
                            }else{
                                printf("%s", &buf[i]);
                            }
                        }else if(i+to_print>=result){
                            new=1;
                            break;
                        }

                        if(i+to_print>=result){ // null was found outside of the message
                            new=0;
                            break;
                        }
                        printf("\n");
                        new=1;
                    }
                }else
                    break;
            }
            printf("Connection closed by client\n");
        }
    } while(1);
    exit(0);
}