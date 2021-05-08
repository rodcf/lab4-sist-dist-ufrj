import socket
import select
import struct
import sys
import threading
import json
from json.decoder import JSONDecodeError

# localizacao do servidor
HOST = '' # '' possibilita acessar qualquer endereco alcancavel da maquina local
PORT = 5000 # porta onde chegarao as mensagens para essa aplicacao

FORMAT = 'utf-8'

HEADER_LENGTH = 4

# lista de entradas (I/O) a serem observados pela aplicacao
inputs = [sys.stdin]

# armazena todas as conexoes estabelecidas ao longo da execucao da aplicacao
connected_clients = {}

online_users = {}

def initialize():

    serverSocket = socket.socket()

    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSocket.setblocking(False)

    serverSocket.bind((HOST, PORT))
    serverSocket.listen(5)

    inputs.append(serverSocket)

    return serverSocket

def acceptConnection(serverSocket):

    socket, address = serverSocket.accept()

    connected_clients[socket] = address

    print('Conexao estabelecida com:', address)

    return socket, address

def recvall(connectionSocket, numBytes):

    # Helper function to recv n bytes or return None if EOF is hit
    data = bytearray()
    while len(data) < numBytes:
        packet = connectionSocket.recv(numBytes - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

def receiveMessage(connectionSocket):

    header = recvall(connectionSocket, HEADER_LENGTH)
    if not header:
        return None
    msgSize = struct.unpack('>I', header)[0]
    # Read the message data
    return recvall(connectionSocket, msgSize)

def handleRequests(connectionSocket, address):

    while True:

        receivedMsg = receiveMessage(connectionSocket)

        if not receivedMsg:

            connectionSocket.close()

            del connected_clients[connectionSocket]

            # imprime mensagem de conexao encerrada
            print('Conexao encerrada com:', address)

            handleLeaveRequest(connectionSocket, address)

            return

        receivedMsgString = receivedMsg.decode(FORMAT)

        # imprime a mensagem recebida
        print(str(address) + ':', receivedMsgString)

        try:
            receivedMsgObject = json.loads(receivedMsgString)

        except JSONDecodeError:
            print('Falha na decodificação da mensagem!')
            continue

        if receivedMsgObject['type'] == 'connection-request':
            handleJoinRequest(connectionSocket, address, receivedMsgObject)
        
        elif receivedMsgObject['type'] == 'disconnection-request':
            handleLeaveRequest(connectionSocket, address)

        elif receivedMsgObject['type'] == 'chat-message':
            handleChatMessage(connectionSocket, address, receivedMsgObject)

        else:
            print(f'Tipo de mensagem "{receivedMsgObject["type"]}" inválido!')
            
def broadcast(connection, msg):

    for socket in connected_clients:
        if connected_clients[socket] in online_users and socket != connection:
            socket.sendall(struct.pack('>I', len(msg)) + msg.encode(FORMAT))

def handleJoinRequest(connectionSocket, address, msgObject):

    username = msgObject['name']

    if username in online_users.values():

        print(f'ERRO: Nome de usuário "{username}" já em uso!')

        connection_response_object = {
            "type": "connection-response",
            "success": False,
            "users_list": None,
            "error_msg": "Nome de usuário já está em uso!\nPor favor, digite outro nome."
        }

    else:

        print(username, 'se conectou!')

        users_list = []

        for user in online_users:
            user_to_list = {
                "host": user[0],
                "port": user[1],
                "name": online_users[user]
            }
            users_list.append(user_to_list)

        connection_response_object = {
            "type": "connection-response",
            "success": True,
            "users_list": users_list,
            "error_msg": None
        }

        online_users[address] = username

        connection_object = {
            "type": "user-joined",
            "name": username,
            "host": address[0],
            "port": address[1]
        }

        connection_msg = json.dumps(connection_object)

        print('Mensagem broadcast enviada:', connection_msg)

        broadcast(connectionSocket, connection_msg)

    connection_response_msg = json.dumps(connection_response_object)

    connectionSocket.sendall(struct.pack('>I', len(connection_response_msg)) + connection_response_msg.encode(FORMAT))

    print('Mensagem enviada:', connection_response_msg)

    print('online_users:', online_users)

def handleLeaveRequest(connectionSocket, address):

    if connectionSocket in connected_clients:

        disconnection_response = {
            "type": "disconnection-response"
        }

        disconnection_response_msg = json.dumps(disconnection_response)

        print('disconnection_response:', disconnection_response_msg)

        connectionSocket.sendall(struct.pack('>I', len(disconnection_response_msg)) + disconnection_response_msg.encode(FORMAT))

    if address in online_users:

        disconnection_broadcast = {
            "type": "user-left",
            "name": online_users[address],
            "host": address[0],
            "port": address[1]
        }
 
        del online_users[address]

        disconnection_broadcast_msg = json.dumps(disconnection_broadcast)

        print('disconnection_broadcast:', disconnection_broadcast_msg)

        print('online_users:', online_users)

        broadcast(connectionSocket, disconnection_broadcast_msg)

def getReceiverSocket(receiver_name):

    if not receiver_name in online_users.values():
        return None
    
    receiver_address = list(online_users.keys())[list(online_users.values()).index(receiver_name)]

    print(f'receiver_address: "{receiver_address}"')
    
    if not receiver_address in connected_clients.values():
        return None
    
    receiver_socket = list(connected_clients.keys())[list(connected_clients.values()).index(receiver_address)]

    return receiver_socket

def handleChatMessage(connectionSocket, address, msgObject):

    message = msgObject['message']
    sender = msgObject['sender']

    if msgObject['private'] == True:

        receiver_name = msgObject['receiver']

        receiver_socket = getReceiverSocket(receiver_name)

        if not receiver_socket:
            return
        
        msg_object = {
            "type": "chat-message",
            "private": True,
            "sender": sender,
            "message": message
        }

        msg_string = json.dumps(msg_object)

        print('chat-message private:', msg_string)

        receiver_socket.sendall(struct.pack('>I', len(msg_string)) + msg_string.encode(FORMAT))

    else:

        msg_object = {
            "type": "chat-message",
            "private": False,
            "sender": sender,
            "message": message
        }

        msg_string = json.dumps(msg_object)

        print('chat-message broadcast:', msg_string)

        broadcast(connectionSocket, msg_string)

def main():

    # armazena as threads criadas para tratar requisicoes
    threads = []

    # inicializa o servidor
    serverSocket = initialize()

    print('O servidor esta pronto para receber conexoes...')

    while True:

        # espera ate que alguma entrada da lista de entradas de interesse esteja pronta
        rList, wList, xList = select.select(inputs, [], [])

        # trata as entradas prontas
        for ready in rList:

            # caso seja um novo pedido de conexao
            if ready == serverSocket:

                # estabelece conexao com o cliente
                connectionSocket, address = acceptConnection(serverSocket)

                # cria uma nova thread para tratar as requisicoes do cliente
                thread = threading.Thread(target=handleRequests, args=(connectionSocket,address))

                # adiciona a nova thread na lista de threads
                threads.append(thread)

                # inicia a thread
                thread.start()

            # caso seja uma entrada padrao
            elif ready == sys.stdin:

                # armazena a entrada padrao
                command = input().lower().strip()

                # caso seja uma solicitacao de encerramento do servidor
                if command == 'exit':

                    print('Aguardando clientes para encerrar servidor...')

                    # aguarda todas as threads (clientes) finalizarem
                    for t in threads:
                        t.join()

                    # encerra o socket do servidor
                    serverSocket.close()

                    print('Servidor encerrado')

                    # encerra a aplicacao
                    sys.exit(0)

main()