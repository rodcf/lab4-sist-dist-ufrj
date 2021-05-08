import socket
import struct
import json
import threading
import sys
import os
from tkinter import *
import tkinter.messagebox
from random import randint
from json.decoder import JSONDecodeError

HOST = 'localhost' # maquina onde esta o servidor
PORT = 5000        # porta que o servidor esta escutando

ADDRESS = (HOST, PORT) # tupla contendo o IP e a porta do servidor

HEADER_LENGTH = 4 # tamanho do header utilizado para enviar o tamanho em bytes da mensagem

FORMAT = 'utf-8' # formato utilizado para codificar/decodificar as mensagens

online_users = {} # dicionário de usuários ativos na sala de bate-papo (endereço e nome de usuário)

# cria socket
clientSocket = socket.socket()

# conecta-se com o servidor
clientSocket.connect(ADDRESS)

# Função para receber 'numBytes' bytes or retornar None se EOF for atingido
def recvall(connectionSocket, numBytes):

    data = bytearray()

    while len(data) < numBytes:
        packet = connectionSocket.recv(numBytes - len(data))

        if not packet:
            return None

        data.extend(packet)

    return data

# Função para receber a mensagem completa de acordo com o tamanho em bytes enviado no header
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

# classe para a interface de usuário oferecida
class GUI:
   
    # construtor
    def __init__(self):
        
        # janela de bate-papo, iniciada de maneira escondida do usuário
        self.Window = Tk()
        self.Window.withdraw()

        # janela de menu da aplicação (login)
        self.login = Toplevel()

        # protocolos para lidar com encerramento de alguma das janelas da aplicação
        self.Window.protocol("WM_DELETE_WINDOW", lambda: self.confirmQuit(self.Window))
        self.login.protocol("WM_DELETE_WINDOW", lambda: self.confirmQuit(self.login))

        # título da janela de menu
        self.login.title("Menu")

        # atributos gráficos da janela de menu
        self.login.resizable(width = True, 
                             height = True)

        self.login.configure(width = 400,
                             height = 300)

        # labels para input de nome de usuário
        self.pls = Label(self.login, 
                       text = "Digite um nome de usuário",
                       justify = CENTER, 
                       font = "Helvetica 14 bold")
          
        self.pls.place(relheight = 0.15,
                       relx = 0.2, 
                       rely = 0.07)

        self.labelName = Label(self.login,
                               text = "Nome: ",
                               font = "Helvetica 12")
          
        self.labelName.place(relheight = 0.2,
                             relx = 0.1, 
                             rely = 0.2)
          
        # campo de input para nome de usuário
        self.entryName = Entry(self.login, 
                             font = "Helvetica 14")
          
        self.entryName.place(relwidth = 0.4, 
                             relheight = 0.12,
                             relx = 0.35,
                             rely = 0.2)
          
        # coloca o foco no campo de input
        self.entryName.focus()
          
        # criação de botão de "Entrar", que chama a função 'loginToChat'
        self.go = Button(self.login,
                         text = "Entrar", 
                         font = "Helvetica 14 bold", 
                         command = lambda: self.loginToChat(self.entryName.get()))
          
        self.go.place(relx = 0.4,
                      rely = 0.55)
                    
        # inicia o loop principal da janela de bate-papo
        self.Window.mainloop()
  
    def loginToChat(self, name):

        self.name = name

        # cria a mensagem de requisição de conexão para o servidor
        msg_object = {
            "type": "connection-request",
            "name": name
        }

        # transforma em uma string em formato JSON
        msg_string = json.dumps(msg_object)
        
        # envia a mensagem de requisição de conexão para o servidor
        clientSocket.sendall(struct.pack('>I', len(msg_string)) + msg_string.encode(FORMAT))

        # imprime a mensagem enviada
        print('Mensagem enviada: ', msg_string)

        try:
            # espera a resposta do servidor (chamada pode ser BLOQUEANTE)
            receivedMsg = receiveMessage(clientSocket) # argumento indica a qtde maxima de bytes da mensagem

            # decodifica a mensagem recebida
            receivedMsgString = receivedMsg.decode(FORMAT)

            # imprime a mensagem recebida
            print('Mensagem recebida:', receivedMsgString)

            try:
                # recupera o objeto da mensagem a partir da string JSON recebida
                receivedMsgObject = json.loads(receivedMsgString)

                # se nome valido, vai pra tela de chat
                # se nao, mostra mensagem de erro e nao muda janela

                if receivedMsgObject['success'] == True:

                    # esconde a janela de menu e passa a mostrar a janela de bate-papo
                    self.login.withdraw()
                    self.layout(name)

                    users_list = receivedMsgObject['users_list']

                    # recuperada a lista de usuários da mensagem e guarda no dicionário 'online_users'
                    for user in users_list:
                        online_users[(user['host'], user['port'])] = user['name']
                        self.listbox.insert(END, f" {user['name']}")
                    
                    print('online_users:', online_users)
                    
                    # thread para receber mensagens do servidor
                    self.rcvThread = threading.Thread(target=self.receive)
                    self.rcvThread.start()

                else:
                    # mostra mensagem de erro (nome de usuário já utilizado)
                    tkinter.messagebox.showerror('Erro', receivedMsgObject['error_msg'])

            except JSONDecodeError:
                print('Falha na decodificação da mensagem!')

        except:
            pass
  
    # função para inserir mensagem na caixa de texto da janela de bate-papo
    def insertMessage(self, display_msg):

        self.textCons.config(state = NORMAL)
        self.textCons.insert(END, display_msg)
        self.textCons.config(state = DISABLED)
        self.textCons.see(END)
    
    # A janela de bate-papo
    def layout(self,name):
        
        self.name = name

        # mostra a janela de bate-papo
        self.Window.deiconify()

        # atribui um título à janela
        self.Window.title("Bate-papo")

        # configurações gráficas da janela de bate-papo
        self.Window.resizable(width = True,
                              height = True)

        self.Window.configure(width = 600,
                              height = 550,
                              bg = "#17202A")        

        self.labelHead = Label(self.Window,
                             bg = "#17202A", 
                             fg = "#EAECEE",
                             text = f'Bem-vindo(a), {self.name}',
                             font = "Helvetica 13 bold",
                             pady = 5)
          
        self.labelHead.place(relwidth = 1,
                             rely = 0.01)

        self.line = Label(self.Window,
                          width = 450,
                          bg = "#ABB2B9")
          
        self.line.place(relwidth = 1,
                        rely = 0.07,
                        relheight = 0.012)

        self.buttonReturn = Button(self.labelHead,
                                text = "Voltar ao menu",
                                font = "Helvetica 10 bold", 
                                width = 20,
                                bg = "#ABB2B9",
                                command = lambda : self.returnToMenu())

        self.buttonReturn.place(relx = 0.77,
                                relheight = 1, 
                                relwidth = 0.22)

        self.textCons = Text(self.Window,
                             width = 20, 
                             height = 2,
                             bg = "#17202A",
                             fg = "#EAECEE",
                             font = "Helvetica 14", 
                             padx = 5,
                             pady = 5)
          
        self.textCons.place(relheight = 0.745,
                            relwidth = 0.72, 
                            rely = 0.08)

        self.listbox = Listbox(self.Window,
                               width = 15, 
                               height = 10, 
                               bg = "#17202A",
                               fg = "#EAECEE",
                               activestyle = 'dotbox', 
                               font = "Helvetica 13")
        
        self.listbox.place(relheight = 0.745,
                           relwidth = 0.25,
                           relx = 0.745,
                           rely = 0.08)
          
        self.labelBottom = Label(self.Window,
                                 bg = "#ABB2B9",
                                 height = 80)
          
        self.labelBottom.place(relwidth = 1,
                               rely = 0.825)
          
        self.entryMsg = Entry(self.labelBottom,
                              bg = "#2C3E50",
                              fg = "#EAECEE",
                              font = "Helvetica 13")
          
        self.entryMsg.place(relwidth = 0.74,
                            relheight = 0.06,
                            rely = 0.008,
                            relx = 0.011)

        self.entryMsg.bind("<Return>", self.onEnterPressed)
          
        self.entryMsg.focus()
          
        # cria o botão de enviar mensagem
        self.buttonMsg = Button(self.labelBottom,
                                text = "Enviar",
                                font = "Helvetica 10 bold", 
                                width = 20,
                                bg = "#ABB2B9",
                                command = lambda : self.sendButton())
          
        self.buttonMsg.place(relx = 0.77,
                             rely = 0.008,
                             relheight = 0.06, 
                             relwidth = 0.22)
          
        self.textCons.config(cursor = "arrow")
          
        # cria a barra de rolagem
        scrollbar = Scrollbar(self.Window)
          
        scrollbar.place(relheight = 0.745,
                        relx = 0.72,
                        rely = 0.08)
          
        scrollbar.config(command = self.textCons.yview)

        # mensagem a ser exibida para o usuário
        display_msg = 'Você se conectou ao bate-papo.\n\n'

        # insere o nome do usuário na lista de usuários ativos
        self.listbox.insert(END, f' {self.name} (Você)')

        self.entryMsg.delete(0, END)

        # insere a mensagem display_msg no bate-papo
        self.insertMessage(display_msg)
    
    # lógica do botão de retornar ao menu
    def returnToMenu(self):

        # cria a mensagem de requisição de saída do bate-papo
        disconnection_request = {
            "type": "disconnection-request"
        }

        # transforma o objeto em uma string JSON
        msg_string = json.dumps(disconnection_request)

        # imprime a mensagem enviada
        print('Mensagem enviada: ', msg_string)

        # envia a mensagem para o servidor
        clientSocket.sendall(struct.pack('>I', len(msg_string)) + msg_string.encode(FORMAT))

        # esconde a janela de bate-papo e passa a mostrar a janela de menu
        self.Window.withdraw()
        self.login.deiconify()

    # lógica do modal de confirmação de encerramento da aplicação (clicar no X)
    def confirmQuit(self, window):
        if tkinter.messagebox.askokcancel("Fechar", "Você tem certeza que deseja fechar a aplicação?"):
            window.destroy()
            os._exit(0)

    def onEnterPressed(self, event):
        self.sendButton()
  
    # função chamada ao clicar no botão de enviar mensagem
    def sendButton(self):

        # recupera a mensagem do campo de input de mensagem
        self.msg = self.entryMsg.get()

        # se mensagem for vazia, não faz nada
        if not self.msg:
            return

        # imprime a mensagem digitada no console
        print('Message:', self.msg)

        self.entryMsg.delete(0, END)

        # chama a função de envio de mensagens para o servidor
        self.sendMessage()
  
    # recebe e trata mensagens do servidor
    def receive(self):

        while True:
            try:

                # recebe a mensagem do servidor
                receivedMsg = receiveMessage(clientSocket)

                # decodifica para uma string JSON
                receivedMsgString = receivedMsg.decode(FORMAT)

                # imprime a mensagem recebida
                print('Mensagem recebida:', receivedMsgString)

                try:
                    # recupera o objeto contido na string JSON
                    receivedMsgObject = json.loads(receivedMsgString)

                except JSONDecodeError:
                    print('Falha na decodificação da mensagem!')
                    continue
                  
                # trata mensagem de notificação de entrada de usuário no bate-papo
                if receivedMsgObject['type'] == 'user-joined':
                    self.handleUserJoined(receivedMsgObject)
        
                # trata mensagem de notificação de saída de usuário do bate-papo
                elif receivedMsgObject['type'] == 'user-left':
                    self.handleUserLeft(receivedMsgObject)

                # trata mensagem de bate-papo recebida
                elif receivedMsgObject['type'] == 'chat-message':
                    self.handleChatMessage(receivedMsgObject)

                # trata mensagem de permissão de desconexão do bate-papo
                elif receivedMsgObject['type'] == 'disconnection-response':
                    # sai do loop de recebimento de mensagens
                    return

                # caso receba um tipo de mensagem desconhecido, imprime mensagem de erro no console
                else:
                    print(f'Tipo de mensagem "{receivedMsgObject["type"]}" inválido!')

            # imprime no console possíveis exceções e encerra conexão com o servidor
            except BaseException as e:
                print(e)
                clientSocket.close()
                break 
          
    # envia a mensagem em self.msg
    def sendMessage(self):

        self.textCons.config(state=DISABLED)

        # trata caso de mensagens privadas
        if(self.msg[:4] == '/mp '):

            try:
                # recupera o índice, na string, do caracter de espaço seguinte ao nome do usuário
                next_space = self.msg.index(' ', 5)
            
            # caso a mensagem contida no comando de mensagem privada seja vazia
            except ValueError:
                display_msg = f'Mensagem privada não deve ser vazia!\n\n'
                self.insertMessage(display_msg)
                return

            # recupera o nome do destinatário da mensagem privada da string do comando
            receiver_name = self.msg[4:next_space]

            # se o destinatário da mensagem privada for o próprio remetente
            if receiver_name == self.name:

                # cria e insere mensagem de erro na janela de bate-papo
                display_msg = f'Usuário inválido para mensagem privada!\n\n'
                self.insertMessage(display_msg)

                return

            # se o destinatário for um usuário ativo no bate-papo
            if receiver_name in online_users.values():

                # recupera a mensagem de texto contida no comando de mensagem privada
                msg = self.msg[next_space+1:]

                # caso a mensagem recuperada seja vazia ou seja formada apenas por whitespace
                if not msg or msg.isspace():

                    # cria e insere mensagem de erro na janela de bate-papo
                    display_msg = f'Mensagem privada não deve ser vazia!\n\n'
                    self.insertMessage(display_msg)

                    return
                
                # formata e insere a mensagem privada na janela de bate-papo
                display_msg = f'Você -> {receiver_name}: {msg}\n\n'
                self.insertMessage(display_msg)

                # cria o objeto da mensagem privada, com os campos devidamente preenchidos
                msg_object = {
                    "type": "chat-message",
                    "private": True,
                    "sender": self.name,
                    "receiver": receiver_name,
                    "message": msg
                }

                # transforma o objeto da mensagem privada em uma string JSON
                msg_string = json.dumps(msg_object)

                # envia a mensagem privada para o servidor, para que ele repasse ao destinatário
                clientSocket.sendall(struct.pack('>I', len(msg_string)) + msg_string.encode(FORMAT))  

            # caso o nome de usuário passado como destinatário não esteja ativo no bate-papo
            else:

                # cria e insere mensagem de erro na janela de bate-papo
                display_msg = f'Usuário "{receiver_name}" não encontrado.\n\n'
                self.insertMessage(display_msg)

        # trata casos de mensagens públicas (broadcast)
        else:

            # formata e insere a mensagem privada na janela de bate-papo
            display_msg = f'Você: {self.msg}\n\n'
            self.insertMessage(display_msg)

            # cria o objeto da mensagem pública, com os campos devidamente preenchidos
            msg_object = {
                "type": "chat-message",
                "private": False,
                "sender": self.name,
                "receiver": None,
                "message": self.msg
            }

            # transforma o objeto da mensagem pública em uma string JSON
            msg_string = json.dumps(msg_object)

            # envia a mensagem pública para o servidor, para que ele a todos os usuários ativos no bate-papo
            clientSocket.sendall(struct.pack('>I', len(msg_string)) + msg_string.encode(FORMAT))  

    # trata mensagem de notificação de entrada de usuário no bate-papo
    def handleUserJoined(self, msgObject):

        # recupera o endereço e o nome de usuário do usuário recém conectado do objeto da mensagem
        new_user_address = (msgObject['host'], msgObject['port'])
        new_user_name = msgObject['name']

        # inclui o usuário no dicionário de usuários ativos no bate-papo
        online_users[new_user_address] = new_user_name

        print('online_users:', online_users)

        # insere o nome do novo usuário na lista de usuários ativos na direita da janela de bate-papo
        self.listbox.insert(END, ' ' + new_user_name)

        # formata e insere a mensagem de notificação de entrada de usuário na caixa de texto da janela de bate-papo
        display_msg = f'{new_user_name} se conectou ao bate-papo.\n\n'
        self.insertMessage(display_msg)
    
    # trata mensagem de notificação de saída de usuário do bate-papo
    def handleUserLeft(self, msgObject):

        # recupera o endereço e o nome de usuário do usuário que saiu do objeto da mensagem
        user_address = (msgObject['host'], msgObject['port'])
        user_name = msgObject['name']

        # exclui o usuário do dicionário de usuários ativos no bate-papo
        del online_users[user_address]

        print('online_users:', online_users)

        # remove o nome do usuário da lista de usuários ativos na direita da janela de bate-papo
        index = self.listbox.get(0, END).index(' ' + user_name)
        self.listbox.delete(index)

        # formata e insere a mensagem de notificação de saída de usuário na caixa de texto da janela de bate-papo
        display_msg = f'{user_name} se desconectou do bate-papo.\n\n'
        self.insertMessage(display_msg)

    # trata mensagem de bate-papo recebida
    def handleChatMessage(self, msgObject):

        # recupera o nome de usuário e mensagem de bate-papo do objeto da mensagem
        sender = msgObject['sender']
        message = msgObject['message']

        # caso a mensagem recebida seja privada
        if msgObject['private']:

            # formata e insere a mensagem privada a caixa de texto da janela de bate-papo
            display_msg = f'{sender} -> Você: {message}\n\n'
            self.insertMessage(display_msg)

        # caso a mensagem recebida seja pública
        else:

            # formata e insere a mensagem pública a caixa de texto da janela de bate-papo
            display_msg = f'{sender}: {message}\n\n'
            self.insertMessage(display_msg)

# instancia a classe de interface de usuário
g = GUI()