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

FORMAT = 'utf-8' # formato utilizado para codificar/decodificar as mensagens

HEADER_LENGTH = 4 # tamanho do header utilizado para enviar o tamanho em bytes da mensagem

# lista de entradas (I/O) a serem observados pela aplicacao
inputs = [sys.stdin]

# armazena os sockets e endereços de clientes atualmente conectados a aplicacao
connected_clients = {}

online_users = {} # dicionário de usuários ativos na sala de bate-papo (endereço e nome de usuário)

def initialize():
    '''Cria um socket para o servidor e o coloca em modo de espera por conexoes
    Saida: o socket de servidor criado'''

    # cria socket
    serverSocket = socket.socket()

    # permite o reuso da porta caso a aplicacao seja finalizada de forma abrupta
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # define o socket do servidor como nao-bloqueante
    serverSocket.setblocking(False)

    # vincula a interface e porta para comunicacao
    serverSocket.bind((HOST, PORT))

    # define o limite maximo de conexoes pendentes e coloca-se em modo de espera por conexao
    serverSocket.listen(5)

    # adiciona o socket do servidor na lista de entradas da aplicacao
    inputs.append(serverSocket)

    return serverSocket

def acceptConnection(serverSocket):
    '''Estabelece conexao com um cliente
    Entrada: o socket do servidor
    Saida: o socket de conexao criado e o endereco (IP, PORTA) do cliente'''

    # Aceita o pedido de conexao do cliente
    socket, address = serverSocket.accept()

    # Armazena o socket e o endereco do cliente no dicinario de conexoes ativas
    connected_clients[socket] = address

    # imprime o par (IP,PORTA) da conexao estabelecida
    print('Conexao estabelecida com:', address)

    return socket, address

# função para receber 'numBytes' bytes or retornar None se EOF for atingido
def recvall(connectionSocket, numBytes):

    data = bytearray()

    while len(data) < numBytes:
        packet = connectionSocket.recv(numBytes - len(data))

        if not packet:
            return None

        data.extend(packet)

    return data

# função para receber a mensagem completa de acordo com o tamanho em bytes enviado no header
def receiveMessage(connectionSocket):

    # recebe o trecho da mensagem relativo ao tamanho da mensagem
    header = recvall(connectionSocket, HEADER_LENGTH)

    # se mensagem recebida for vazia, retorna None
    if not header:
        return None

    # desempacota os 4 bytes do header que contém o tamanho da mensagem
    msgSize = struct.unpack('>I', header)[0]

    # recebe o restante da mensagem, de tamanho msgSize
    return recvall(connectionSocket, msgSize)

def handleRequests(connectionSocket, address):
    '''Recebe e processa mensagens do cliente, tratando suas diferentes requisições e 
    enviando para ele os retornos gerados pela aplicacao para a mensagem recebida
    Entrada: o socket da conexao e o endereco do cliente'''

    while True:

        # recebe a mensagem do cliente
        receivedMsg = receiveMessage(connectionSocket)

        # caso receba dados vazios: cliente encerrou a conexao
        if not receivedMsg:

            # fecha o socket da conexao
            connectionSocket.close()

            # retira a entrada referente ao cliente do dicionario de conexoes atuais
            del connected_clients[connectionSocket]

            # imprime mensagem de conexao encerrada
            print('Conexao encerrada com:', address)

            # trata requisições de saída do bate-papo 
            handleLeaveRequest(connectionSocket, address)

            return

        # transforma a mensagem em uma string JSON
        receivedMsgString = receivedMsg.decode(FORMAT)

        # imprime a mensagem recebida
        print(str(address) + ':', receivedMsgString)

        try:
            # recupera o objeto contido na string JSON
            receivedMsgObject = json.loads(receivedMsgString)

        except JSONDecodeError:
            print('Falha na decodificação da mensagem!')
            continue

        # trata requisição de entrada de usuário no bate-papo
        if receivedMsgObject['type'] == 'connection-request':
            handleJoinRequest(connectionSocket, address, receivedMsgObject)
        
        # trata requisição de saída de usuário do bate-papo
        elif receivedMsgObject['type'] == 'disconnection-request':
            handleLeaveRequest(connectionSocket, address)

        # trata as mensagens de bate-papo recebidas
        elif receivedMsgObject['type'] == 'chat-message':
            handleChatMessage(connectionSocket, address, receivedMsgObject)

        # caso receba um tipo de mensagem desconhecido, imprime mensagem de erro no console
        else:
            print(f'Tipo de mensagem "{receivedMsgObject["type"]}" inválido!')
            
# função para fazer o broadcast da mensagem 'msg' para todos os clientes com exceção daquele de socket 'connection'
def broadcast(connection, msg):

    # percorre os sockets de conexão dos clientes atualmente conectados ao servidor
    for socket in connected_clients:

        # se esse socket corresponde a um usuário ativo no bate-papo, diferente de quem enviou a mensagem
        if connected_clients[socket] in online_users and socket != connection:

            # envia a mensagem para esse usuário
            socket.sendall(struct.pack('>I', len(msg)) + msg.encode(FORMAT))

# trata requisição de entrada de usuário no bate-papo
def handleJoinRequest(connectionSocket, address, msgObject):

    # recupera o nome do usuário do objeto da mensagem
    username = msgObject['name']

    # se o nome de usuário já está em uso
    if username in online_users.values():

        # imprime mensagem de erro no console
        print(f'ERRO: Nome de usuário "{username}" já em uso!')

        # cria objeto com dados de resposta de conexão contendo a mensagem de erro
        connection_response_object = {
            "type": "connection-response",
            "success": False,
            "users_list": None,
            "error_msg": "Nome de usuário já está em uso!\nPor favor, digite outro nome."
        }

    # se o nome de usuário não estiver em uso
    else:

        print(username, 'se conectou!')

        # cria uma lista vazia para armazenar os usuários ativos
        # é necessário enviar uma lista pois não existem tuplas no formato JSON,
        # e o dicionario 'online_users' tem como chave as tuplas de endereço dos usuários
        users_list = []

        # preenche a lista de usuários ativos a partir do dicionario 'online_users'
        for user in online_users:
            user_to_list = {
                "host": user[0],
                "port": user[1],
                "name": online_users[user]
            }
            users_list.append(user_to_list)

        # cria objeto de resposta de sucesso de conexão
        connection_response_object = {
            "type": "connection-response",
            "success": True,
            "users_list": users_list,
            "error_msg": None
        }

        # adiciona o usuário no dicionário de usuários ativos no bate-papo
        online_users[address] = username

        # cria objeto de notificação de entrada de novo usuário no bate-papo
        connection_object = {
            "type": "user-joined",
            "name": username,
            "host": address[0],
            "port": address[1]
        }

        # transforma o objeto de notificação de entrada de usuário em uma string JSON
        connection_msg = json.dumps(connection_object)

        print('Mensagem broadcast enviada:', connection_msg)

        # envia a notificação de entrada de novo usuário para todos os outros usuários ativos
        broadcast(connectionSocket, connection_msg)

    # transforma o objeto de resposta de conexão em uma string JSON
    connection_response_msg = json.dumps(connection_response_object)

    # envia a resposta de conexão (sucesso ou falha) para o cliente
    connectionSocket.sendall(struct.pack('>I', len(connection_response_msg)) + connection_response_msg.encode(FORMAT))

    print('Mensagem enviada:', connection_response_msg)

    print('online_users:', online_users)

# trata requisição de saída de usuário do bate-papo
def handleLeaveRequest(connectionSocket, address):

    # caso o socket do cliente que deseja sair esteja no dicionário de conexões atuais
    if connectionSocket in connected_clients:

        # cria objeto de resposta de desconexão
        disconnection_response = {
            "type": "disconnection-response"
        }

        # transforma o objeto de resposta de desconexão em uma string JSON
        disconnection_response_msg = json.dumps(disconnection_response)

        print('disconnection_response:', disconnection_response_msg)

        # envia a resposta de desconexão para o cliente que a solicitou
        connectionSocket.sendall(struct.pack('>I', len(disconnection_response_msg)) + disconnection_response_msg.encode(FORMAT))

    # caso o usuário esteja no dicionário de usuários ativos na sala de bate-papo
    # retorno para o menu / encerramento da aplicação diretamente da janela de bate-papo
    if address in online_users:

        # cria objeto de notificação de saída de usuário do bate-papo
        disconnection_broadcast = {
            "type": "user-left",
            "name": online_users[address],
            "host": address[0],
            "port": address[1]
        }
 
        # remove o usuário do dicionário de usuários ativos no bate-papo
        del online_users[address]

        # transforma o objeto de notificação de saída de usuário em uma string JSON
        disconnection_broadcast_msg = json.dumps(disconnection_broadcast)

        print('disconnection_broadcast:', disconnection_broadcast_msg)

        print('online_users:', online_users)

        # envia a notificação de saída de usuário para todos os outros usuários ativos
        broadcast(connectionSocket, disconnection_broadcast_msg)

# função para recuperar, a partir do nome de um usuário, seu socket de conexão com o servidor
def getReceiverSocket(receiver_name):

    # se usuário não estiver ativo, retorna None
    if not receiver_name in online_users.values():
        return None
    
    # recupera o endereço do usuário a partir do seu nome
    receiver_address = list(online_users.keys())[list(online_users.values()).index(receiver_name)]

    print(f'receiver_address: "{receiver_address}"')
    
    # se usuário não estiver com conexão ativa com o servidor, retorna None
    if not receiver_address in connected_clients.values():
        return None
    
    # recupera o socket de conexão do usuário a partir do seu endereço
    receiver_socket = list(connected_clients.keys())[list(connected_clients.values()).index(receiver_address)]

    return receiver_socket

# função para tratar as mensagens de bate-papo recebidas pelo servidor
def handleChatMessage(connectionSocket, address, msgObject):

    # recupera o texto e o nome do remetente da mensagem do objeto
    message = msgObject['message']
    sender = msgObject['sender']

    # caso a mensagem seja privada
    if msgObject['private'] == True:

        # recupera o nome do destinatário da mensagem privada
        receiver_name = msgObject['receiver']

        # recupera o socket do destinatário da mensagem privada
        receiver_socket = getReceiverSocket(receiver_name)

        # se não encontrar o socket do destinatário, retorna
        if not receiver_socket:
            return
        
        # cria o objeto da mensagem privada de bate-papo
        msg_object = {
            "type": "chat-message",
            "private": True,
            "sender": sender,
            "message": message
        }

        # transforma o objeto da mensagem privada de bate-papo em uma string JSON
        msg_string = json.dumps(msg_object)

        print('chat-message private:', msg_string)

        # envia a mensagem privada para o destinatário correspondente
        receiver_socket.sendall(struct.pack('>I', len(msg_string)) + msg_string.encode(FORMAT))

    # caso a mensagem seja pública
    else:

        # cria o objeto da mensagem pública de bate-papo
        msg_object = {
            "type": "chat-message",
            "private": False,
            "sender": sender,
            "message": message
        }

        # transforma o objeto da mensagem pública de bate-papo em uma string JSON
        msg_string = json.dumps(msg_object)

        print('chat-message broadcast:', msg_string)

        # envia a mensagem pública para todos os usuários ativos no bate-papo, com exceção de quem a enviou
        broadcast(connectionSocket, msg_string)

def main():
    '''Loop principal do servidor'''

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

# inicia o loop principal da aplicacao
main()