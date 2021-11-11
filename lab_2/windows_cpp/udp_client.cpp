#include<Windows.h>
#include<winsock.h>
#include<iostream>

using namespace std;


struct SendMeBabe {
	long long int a;
	int b;
	short int c;
	short int d;
	char e[8];
};  // 24 bytes - no padding between values



int main() {


	WSADATA		WinSockData;
	int			iWsaStartup;
	int			iWsaCleanup;

	SOCKET		UDPSocketClient;
	struct		sockaddr_in	UDPServer;

	int			iSendto;

	int			iUDPServerLen = sizeof(UDPServer);
	int			iCloseSocket;


	// Structure to be send
	SendMeBabe babe = { 12345678910, 333444, 66, 33, "Hello!!"};
	int iBabeLen = sizeof(babe);


	// Init of Winsock ------------------------------------------------------------------------
	iWsaStartup = WSAStartup(MAKEWORD(2, 2), &WinSockData);
	if (iWsaStartup != 0)
	{
		cout << "WSAStartup failed = " << iWsaStartup << endl;
	}

	cout << "WSAStartup Success" << endl;


	// Fill the UDPServer struct ---------------------------------------------------------------
	UDPServer.sin_family		= AF_INET;
	UDPServer.sin_addr.s_addr	= inet_addr("127.0.0.1");
	UDPServer.sin_port = htons(65000);


	// Socket Creation -------------------------------------------------------------------------
	UDPSocketClient = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
	if (UDPSocketClient == INVALID_SOCKET)
	{
		cout << "UDP Socket creation failed = " << WSAGetLastError() << endl;
	}


	// Sendto function -------------------------------------------------------------------------
	iSendto = sendto(UDPSocketClient, (char*)&babe, iBabeLen, MSG_DONTROUTE, (SOCKADDR*)&UDPServer, sizeof(UDPServer));
	if (iSendto == SOCKET_ERROR)
	{
		cout << "Sending data failed & Error No->" << WSAGetLastError() << endl;
	}


	cout << "Sending data success" << endl;


	// Close socket ----------------------------------------------------------------------------
	iCloseSocket = closesocket(UDPSocketClient);
	if (iCloseSocket == SOCKET_ERROR)
	{
		cout << "Close Socket Failed = " << WSAGetLastError() << endl;
	}

	cout << "Close Socket Success" << endl;


	// WSACleanUp function for terminating -----------------------------------------------------
	iWsaCleanup = WSACleanup();
	if (iWsaCleanup == SOCKET_ERROR)
	{
		cout << "CleanUp failed = " << WSAGetLastError() << endl;
	}

	cout << "CleanUp Success" << endl;

}