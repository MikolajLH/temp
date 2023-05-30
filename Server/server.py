import os
import sys
import inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

import protocol
import utility
import selectors
import socket
from games_manager import GameManager
from account_manager import AccountManager
import Parameters
import time


CONSOLE_LISTENER = 1
CONSOLE_TO_SERVER = 2

CLIENT_LISTENER = 3
CLIENT_TO_SERVER = 4

class Server:
    def __init__(self, host : str, port : int):
        self.__running : bool = False

        self.__console_listener : socket.socket|None = protocol.create_listening_socket(host, port)
        if self.__console_listener is None:
            exit(-1)

        self.__console_to_server_sock : socket.socket|None = None
        

        print(f"[Info]: Waiting for console to connect at {self.__console_listener.getsockname()}")

        self.__clients_listener : socket.socket|None = None
        self.__clients_sockets : dict[int,socket.socket] = dict()
        self.__clients_accounts : dict[int, AccountManager] = dict()

        self.__clients_counter : int = 0

        self.__games_manager = GameManager()
        self.__process = False

        

        self.__sel : selectors.DefaultSelector|None = selectors.DefaultSelector()
        self.__sel.register(self.__console_listener, selectors.EVENT_READ, data=(CONSOLE_LISTENER, -1))

    def run(self):
        self.__running = True
        #self.__games_manager.load()

        start_time = time.time_ns()
        wait_time = 10

        while self.__running:
            current_time = time.time_ns()
            if (current_time - start_time) >= wait_time:
                start_time = current_time
                if self.__games_manager is not None:
                    if self.__process:
                        try:
                            res = self.__games_manager.process_all()
                            print(res)
                        except:
                            pass



            events = self.__sel.select(0.5)
            for key, _ in events:
                sock : socket.socket = key.fileobj
                #socket id is only valid for CLIENT_TO_SERVER sockets, since it is a key in clients dictionary
                sock_type, sock_id = key.data

                #handle all type of sockets
                if sock_type == CONSOLE_LISTENER:
                    self.__accept_console()
                    
                elif sock_type == CONSOLE_TO_SERVER:
                    if(msg := protocol.recv_msg(self.__console_to_server_sock)) is not None:
                        print("[CONSOLE]>>", msg)
                        self.__handle_console_msg(msg)
                    else:
                        self.__disconnect_console()


                elif sock_type == CLIENT_LISTENER:
                    self.__accept_client()
                elif sock_type == CLIENT_TO_SERVER:
                    id = sock_id
                    if (msg := protocol.recv_msg(sock)) is not None:
                        usr_name = id if not self.__clients_accounts[id].logged_in else self.__clients_accounts[id].login
                        print(f"[{usr_name}]: {msg}")
                        self.__handle_client_msg(sock_id, msg)
                    else:
                        print(f"Couldn't receive message from client {sock_id}")
                        self.__safe_disconnect_client(sock_id)
                    pass

    # Console part
    def __accept_console(self):
        conn, addr = self.__console_listener.accept()
        if self.__is_console_connected():
            self.__disconnect_console()

        self.__console_to_server_sock = conn
        self.__console_to_server_sock.settimeout(protocol.TIMEOUT)

        if(sent_successfully := protocol.send_byte(self.__console_to_server_sock, protocol.SERVER_ID)):
            print(f"[Info]: Console connected at {addr}")
            self.__sel.register(self.__console_to_server_sock, selectors.EVENT_READ, data=(CONSOLE_TO_SERVER, -1))
        else:
            print("[Error]: Server ID couldn't be send to console, console disconnecting")
            self.__console_to_server_sock.close()
            self.__console_to_server_sock = None

    def __is_console_connected(self) -> bool:
        return self.__console_to_server_sock is not None
    
    def __handle_console_msg(self, msg : str):
        match msg.split():
            case ["sys", *args] if len(args) > 0:
                os.system(" ".join(args))

            case [protocol.SHUTDOWN_MSG]:
                self.close_server()

            case [protocol.CONSOLE_DSC_MSG]:
                self.__disconnect_console()

            case ["listen", host, port]:
                if (args := utility.silent_convert((host, str), (port, int))) is not None:
                    self.__start_listening(*args)
                else:
                    print("[Info]: Usage listen <host : str> <port : int>")
            
            case ["dsc", client_id]:
                if (args := utility.silent_convert((client_id, int))) is not None:
                    self.__safe_disconnect_client(*args)
                else:
                    print("[Info]: Usage dsc <client_id : int>")

            case ["info"]:
                print(f"Currently there are {len(self.__clients_sockets)} clients connected")


            case ["process"]:
                self.__process = not self.__process
                print(f"[Info]: Process is now {self.__process}")

            case []:
                pass

            case _:
                pass

    def __disconnect_console(self):
        self.__safe_unregister_and_close(self.__console_to_server_sock)
        self.__console_to_server_sock = None
        print("[Info]: Console disconnected")

    # end of Console part

    # Client server communication part

    def __start_listening(self, host : str, port : int):
        if self.__is_listening():
            print("[Info]: Already listening for clients")
            return
        self.__clients_listener = protocol.create_listening_socket(host, port)
        if self.__clients_listener is None:
            print("[Error]: Server can't start listening for clients")
            return
        self.__sel.register(self.__clients_listener, selectors.EVENT_READ, data= (CLIENT_LISTENER, -1))
        print(f"[Info]: Listening for clients at {self.__clients_listener.getsockname()}")


    def __is_listening(self) -> bool:
        return self.__clients_listener is not None
    
    def __get_unique_client_id(self) -> int:
        id = self.__clients_counter
        self.__clients_counter += 1
        return id
    
    def __accept_client(self):
        try:
            conn, addr = self.__clients_listener.accept()
            client_id : int = self.__get_unique_client_id()
            conn.settimeout(protocol.TIMEOUT)
            self.__clients_sockets[client_id] = conn
            self.__clients_accounts[client_id] = AccountManager()
            self.__sel.register(conn, selectors.EVENT_READ, data=(CLIENT_TO_SERVER, client_id))
        except Exception as e:
            print(f"[Exception] __accept_client(): {e}")
            self.__safe_disconnect_client(client_id)
            return
        
        #TODO CLIENT MANAGER
        print(f"[Info]: Accepted new client, addr: {addr}, ID: {client_id}")
        if not (sent_successfully := protocol.send_msg(conn, f"{client_id}")):
            print("[Error]: Couldn't send ID to client")
            self.__safe_disconnect_client(client_id)

    def __send_byte_to_client(self, id : int, byte : bytes, err_msg : str = ""):
        if id in self.__clients_sockets.keys():
            if not (sent_successfully := protocol.send_byte(self.__clients_sockets[id], byte)):
                print("[Error]: Couldn't send byte to client", err_msg)
                self.__safe_disconnect_client(id)
        
    def __send_msg_to_client(self, id : int, msg : str, err_msg : str = ""):
        if id in self.__clients_sockets.keys():
            if not (sent_successfully := protocol.send_msg(self.__clients_sockets[id], msg)):
                print("[Error]: Couldn't send msg to client", err_msg)
                self.__safe_disconnect_client(id)

    def __disconnect_all_clients(self):
        for sock in list(self.__clients_sockets.values()):
            self.__safe_unregister_and_close(sock)

        self.__clients_sockets = dict()
        

    def __safe_disconnect_client(self, client_id : int):
        if client_id in self.__clients_sockets.keys():
            self.__safe_unregister_and_close(self.__clients_sockets[client_id])
            del self.__clients_sockets[client_id]
            del self.__clients_accounts[client_id]
            
            #TODO CLIENT MANAGER
            print(f"[Info]: Client with ID {client_id} just disconnected")
        else:
            print("[Error]: tried to disconnect client who does not exist")

    
    def __handle_client_msg(self, id : int, msg : str):
        match msg.split():
            case ["register", login, password]:
                self.__register(id, login, password)

            case ["login", login, password]:
                self.__login(id, login, password)

            case ["create", game_password]:
                self.__create_new_game(id, game_password)

            case ["join", game_id, game_password, color]:
                if (args := utility.silent_convert((game_id, int))) is not None:
                    self.__join_game(id, *args, game_password, color)
            
            case ["vote", game_id, move]:
                if (args := utility.silent_convert((game_id, int))) is not None:
                    self.__vote(id, *args, move)
            
            case ["rf", game_id]:
                if (args := utility.silent_convert((game_id, int))) is not None:
                    self.__send_byte_to_client(id, protocol.CONFIRMATION_BYTE)
                    game_fen = self.__games_manager.get_game(*args).get_fen()
                    print("[Info]: sending", game_fen)
                    self.__send_msg_to_client(id, protocol.FEN_PREFIX + game_fen)

            case [protocol.CLIENT_DSC_MSG]:
                self.__send_byte_to_client(id, protocol.CONFIRMATION_BYTE)
                self.__safe_disconnect_client(id)
            case _:
                self.__send_byte_to_client(id, protocol.CONFIRMATION_BYTE)
                pass
    


    def __register(self, socket_id : int, login : str, password : str):
        if self.__clients_accounts[socket_id].logged_in:
                self.__send_msg_to_client(socket_id, "You are already logged in")
        else:
            try:
                self.__clients_accounts[socket_id].create_account(login, password)
                self.__send_byte_to_client(socket_id, protocol.CONFIRMATION_BYTE)
                print("[Info]: New user registered")
            except:
                self.__send_byte_to_client(socket_id, protocol.FAILURE_BYTE)
                print("[Info]: Unable to register")

    def __login(self, socket_id : int, login : str, password : str):
        if self.__clients_accounts[socket_id].logged_in:
            self.__send_msg_to_client(socket_id, "You are already logged in")
        else:
            if self.__clients_accounts[socket_id].login_now(login, password):
                self.__clients_accounts[socket_id].load()
                self.__send_byte_to_client(socket_id, protocol.CONFIRMATION_BYTE)
                self.__send_msg_to_client(socket_id, f"Hello {login}")
            else:
                self.__send_byte_to_client(socket_id, protocol.FAILURE_BYTE)

    def __create_new_game(self, socket_id : int, game_password : str):
        if self.__clients_accounts[socket_id].logged_in:
            #TODO user id socket id shouldn't be the same
            game_id = self.__games_manager.new_game(id, game_password)
            self.__send_byte_to_client(socket_id, protocol.CONFIRMATION_BYTE)
            self.__send_msg_to_client(socket_id, f"Your game ID is {game_id}")
        else:
            self.__send_byte_to_client(socket_id, protocol.FAILURE_BYTE)


    def __join_game(self, socket_id : int, game_id : int, game_password : str, color : str):
        if self.__clients_accounts[socket_id].logged_in:
            color = "b" if color.lower() != "w" else "w"
            try:
                self.__games_manager.join_game(game_id, color, game_password, self.__clients_accounts[socket_id])
                self.__send_byte_to_client(socket_id, protocol.CONFIRMATION_BYTE)
                game_fen = self.__games_manager.get_game(game_id).get_fen()
                self.__send_msg_to_client(socket_id, protocol.FEN_PREFIX + game_fen)
            except:
                self.__send_byte_to_client(socket_id, protocol.FAILURE_BYTE)
                self.__send_msg_to_client(socket_id, "Wrong game password")
        else:
            self.__send_byte_to_client(socket_id, protocol.FAILURE_BYTE)

    def __vote(self, socket_id : int, game_id : int, move : str):
        if self.__clients_accounts[socket_id].logged_in:
            print(f"{self.__clients_accounts[socket_id].login} wants to vote on {move}")
            try:
                am = self.__clients_accounts[socket_id]
                color = am.get_color(game_id)
                self.__games_manager.vote(game_id, color == "w", move, am)
                self.__send_byte_to_client(socket_id, protocol.CONFIRMATION_BYTE)
                self.__send_msg_to_client(socket_id, f"You have voted on {move}")
            except:
                self.__send_byte_to_client(socket_id, protocol.FAILURE_BYTE)
        else:
            self.__send_byte_to_client(socket_id, protocol.FAILURE_BYTE)



    # end of Client Server communication part


    def __safe_unregister_and_close(self, sock : socket.socket|None):
        if self.__sel is not None and sock is not None:
            self.__sel.unregister(sock)
            sock.close()

        
    def close_server(self):
        if self.__sel is not None:
            print("[Info]: Closing server")
            
            self.__running = False

            self.__safe_unregister_and_close(self.__console_listener)
            self.__console_listener = None

            self.__safe_unregister_and_close(self.__console_to_server_sock)
            self.__console_to_server_sock = None

            # TODO add disconnecing all clients

            self.__sel.close()
            self.__sel = None
            print("[Info]: Server closed")




if __name__ == "__main__":

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <console_port> \n e.g. {sys.argv[0]} 5051")
        sys.exit(1)

    server = Server("127.0.0.1", int(sys.argv[1]))

    try:
        server.run()
    except KeyboardInterrupt:
        print("\nCaught keyboard interrupt, exiting")
    except Exception as e:
        print("\n[Exception]:", e)
    finally:
        server.close_server()
        