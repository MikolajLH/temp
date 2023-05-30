
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
import chess
import pygame


CHESSBOARD_IMG_PATH = "chesscom_board.png"
PIECES_IMG_PATH = "ChessPiecesArray.png"
SQUARE_SIZE = 60
PIECE_SIZE = 60
CHESSBOARD_SIZE=  8 * SQUARE_SIZE

PIECES_COORDS = { 'q' : (0,0), "k" : (1,0), "r" : (2,0), "n" : (3,0), "b" : (4,0), "p" : (5,0),
                  'Q' : (0,1), "K" : (1,1), "R" : (2,1), "N" : (3,1), "B" : (4,1), "P" : (5,1) }


WHITE = True
BLACK = False


CONSOLE_LISTENER = 0
CONSOLE_TO_CLIENT = 1
SERVER_TO_CLIENT = 2


class ChessApp:

    STATE_CONNECT = 0
    STATE_LOGIN = 1
    STATE_ACCOUNT = 2
    STATE_GAME = 3

    def __init__(self, host : str, port : int):
        pygame.init()
        self.__running = False

        self.__console_listener : socket.socket|None = protocol.create_listening_socket(host, port)
        if self.__console_listener is None:
            exit(-1)

        self.__console_to_client_sock : socket.socket|None = None
        self.__id : int|None = None
        
        print(f"[Info]: Waiting for console to connect at {self.__console_listener.getsockname()}")

        self.__server_to_client_sock : socket.socket|None = None

        self.__sel : selectors.DefaultSelector|None = selectors.DefaultSelector()
        self.__sel.register(self.__console_listener, selectors.EVENT_READ, data=CONSOLE_LISTENER)

        self.__active_game_id : int|None = None
        self.__in_game : bool = False
        self.__selected_square = None
        self.__current_gameboard : chess.Board = chess.Board(chess.STARTING_FEN)
        self.__current_color = WHITE
        self.__current_perspective = WHITE

        self.__chessboard_white_img = pygame.image.load(CHESSBOARD_IMG_PATH)
        self.__chessboard_black_img = pygame.transform.flip(self.__chessboard_white_img, True, True)
        self.__pieces_img = pygame.image.load(PIECES_IMG_PATH)

        self.state = ChessApp.STATE_CONNECT

    def start(self):
        self.__screen = pygame.display.set_mode((CHESSBOARD_SIZE, CHESSBOARD_SIZE))
        self.__running = True
        while self.__running:
            events = self.__sel.select(0.01)
            for key, _ in events:
                sock : socket.socket = key.fileobj
                sock_type = key.data

                if sock_type == CONSOLE_LISTENER:
                    self.__accept_console()
                    
                elif sock_type == CONSOLE_TO_CLIENT:
                    if(msg := protocol.recv_msg(self.__console_to_client_sock)) is not None:
                        print("[CONSOLE]>>", msg)
                        if self.__is_connected():
                            if (successfully_sent := protocol.send_msg(self.__server_to_client_sock, msg)):
                                if (byte := protocol.recv_byte(self.__server_to_client_sock)) is not None:
                                    self.__handle_sent_msg(msg, byte == protocol.FAILURE_BYTE)
                                else:
                                    print("[Error]: Couldn't receive confirmation byte")
                                    self.__disconnect_from_server()

                            pass
                        else:
                            self.__handle_console_msg(msg)
                    else:
                        self.__disconnect_console()

                elif sock_type == SERVER_TO_CLIENT:
                    if(msg := protocol.recv_msg(self.__server_to_client_sock)) is not None:
                        if(msg.startswith(protocol.FEN_PREFIX)):
                            fen = msg[len(protocol.FEN_PREFIX):]
                            self.__current_gameboard = chess.Board(fen)
                            print(f"[Info]: This game ID: {self.__active_game_id}")
                        else:
                            print(msg)
                    else:
                        print("[Error]: Couldn't receive message from server")
                        self.__disconnect_from_server()


            self.__draw_board()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.__running = False
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = pygame.mouse.get_pos()
                    self.__on_lmb_down(x,y)

            if self.__selected_square is not None:
                self.__highlight_legal_moves(*self.__selected_square)

            pygame.display.update()


    # drawing routines

    def __draw_board(self):
        if self.__current_gameboard is None:
            return
        
        if self.__current_perspective == WHITE:
            self.__screen.blit(self.__chessboard_white_img, (0,0))
        elif self.__current_perspective == BLACK:
            self.__screen.blit(self.__chessboard_black_img, (0,0))
        
        for r in range(8):
            for f in range(8):
                piece = self.__current_gameboard.piece_at(8 * r + f)
                if piece is None: continue
                i, j = PIECES_COORDS[str(piece)]
                piece_rect = pygame.Rect(i * PIECE_SIZE, j * PIECE_SIZE, PIECE_SIZE, PIECE_SIZE)
                x,y = self.__square_to_pixels(f,r)
                
                

                self.__screen.blit(self.__pieces_img, (x,y), piece_rect)

    def __get_square(self, x : int, y : int) -> tuple[int,int]:
        if self.__current_perspective == WHITE:
            rank = 7 -  y // SQUARE_SIZE
            file = x // SQUARE_SIZE
        else:
            rank = y // SQUARE_SIZE
            file = 7 - x // SQUARE_SIZE
        return file, rank
        

    def __square_to_pixels(self, file : int, rank : int) -> tuple[int,int]:
        if self.__current_perspective == WHITE:
            x = file * SQUARE_SIZE
            y = CHESSBOARD_SIZE - SQUARE_SIZE - rank * SQUARE_SIZE
        else:
            x = CHESSBOARD_SIZE - SQUARE_SIZE - file * SQUARE_SIZE
            y = rank * SQUARE_SIZE

        return x, y
    
    def __draw_circle(self, file : int, rank : int, radius : int, color : tuple[int,int,int] = (200,200,200)):
        x0, y0 = self.__square_to_pixels(file, rank)
        pygame.draw.circle(self.__screen, color, (x0 + SQUARE_SIZE * 0.5, y0 + SQUARE_SIZE * 0.5), radius)

    
    def __highlight_legal_moves(self, file : int, rank : int):
        piece = self.__current_gameboard.piece_at(rank * 8 + file)
        if piece is None:
            return
        
        square_name = chess.square_name(chess.square(file,rank))
        vms = list(filter(lambda w: w.startswith(square_name), map(chess.Move.uci, self.__current_gameboard.legal_moves)))
        for sq in vms :
            sq = sq[len(square_name):]
            square = chess.parse_square(sq)
            r = chess.square_rank(square)
            f = chess.square_file(square)
            self.__draw_circle(f, r, 10, (100,0,0))

    # end of drawing routines

    def get_legal_squares(self, file : int, rank : int):
        res = []
        piece = self.__current_gameboard.piece_at(rank * 8 + file)
        if piece is None:
            return res
        square_name = chess.square_name(chess.square(file,rank))
        vms = list(filter(lambda w: w.startswith(square_name), map(chess.Move.uci, self.__current_gameboard.legal_moves)))
        
        for sq in vms :
            sq = sq[len(square_name):]
            square = chess.parse_square(sq)
            r = chess.square_rank(square)
            f = chess.square_file(square)
            res += [(f,r)]

        return res


    def __on_lmb_down(self, x : int, y : int):
        new_f, new_r = self.__get_square(x, y)
        new_piece = self.__current_gameboard.piece_at(new_r * 8 + new_f)

        if self.__selected_square is not None:
            if (new_f, new_r) in self.get_legal_squares(*self.__selected_square):
                move = chess.square_name(chess.square(*self.__selected_square)) + chess.square_name(chess.square(new_f,new_r))

                if self.__is_connected() and self.__active_game_id is not None:
                    msg = f"vote {self.__active_game_id} {move}"
                    if (successfully_sent := protocol.send_msg(self.__server_to_client_sock, msg)):
                        if (byte := protocol.recv_byte(self.__server_to_client_sock)) is not None:
                            if byte == protocol.FAILURE_BYTE:
                                self.__disconnect_from_server()
                            else:
                                self.__current_gameboard.push_uci(move)

                self.__selected_square = None
                #self.__current_color = not self.__current_color

                #self.__current_perspective = not self.__current_perspective

            else:
                self.__selected_square = None
        elif new_piece is not None and new_piece.color == WHITE: #self.__current_color:
            self.__selected_square = (new_f, new_r)

    # Console part
    def __accept_console(self):
        conn, addr = self.__console_listener.accept()
        if self.__is_console_connected():
            self.__disconnect_console()

        self.__console_to_client_sock = conn
        self.__console_to_client_sock.settimeout(protocol.TIMEOUT)

        if(sent_successfully := protocol.send_byte(self.__console_to_client_sock, protocol.CLIENT_ID)):
            print(f"[Info]: Console connected at {addr}")
            self.__sel.register(self.__console_to_client_sock, selectors.EVENT_READ, data=CONSOLE_TO_CLIENT)
        else:
            print("[Error]: CLient ID couldn't be send to console, console disconnecting")
            self.__console_to_client_sock.close()
            self.__console_to_client_sock = None

    def __is_console_connected(self) -> bool:
        return self.__console_to_client_sock is not None
    
    def __handle_console_msg(self, msg : str):
        match msg.split():
            case ["sys", *args] if len(args) > 0:
                os.system(" ".join(args))

            case [protocol.SHUTDOWN_MSG]:
                self.close_server()

            case [protocol.CONSOLE_DSC_MSG]:
                self.__disconnect_console()

            case ["conn", host, port]:
                if (args := utility.silent_convert((host, str), (port, int))) is not None:
                    self.__connect_to_server(*args)
                else:
                    print("[Info]: Usage conn <host : str> <port : int>")
            case _:
                pass

    def __disconnect_console(self):
        self.__safe_unregister_and_close(self.__console_to_client_sock)
        self.__console_to_client_sock = None
        print("[Info]: Console disconnected")

    # end of Console part


    def __connect_to_server(self, host : str, port : int):
        if self.__is_connected():
            print(f"[Error]: Already connected to server: {self.__server_to_client_sock.getsockname()}")
            return
        try:
            self.__server_to_client_sock = protocol.create_socket()
            self.__server_to_client_sock.connect((host, port))
            print(f"[Info]: Connected to server {(host, port)}")

            if(client_id := protocol.recv_msg(self.__server_to_client_sock)) is not None:
                if (args := utility.silent_convert((client_id, int))) is not None:
                    self.__id, *_ = args
                    print(f"[Server]: Client ID: {self.__id}")
                else:
                    print("[Error]: Wrong type of client ID")
                    self.__disconnect_from_server()
            else:
                print("[Error]: Server did not send client ID")
        except Exception as e:
            print(f"[Exception] __connect_to_server(): {e}")
            self.__server_to_client_sock.close()
            self.__server_to_client_sock = None

        self.__sel.register(self.__server_to_client_sock, selectors.EVENT_READ, data=SERVER_TO_CLIENT)

    def __is_connected(self):
        return self.__server_to_client_sock is not None
    
    def __disconnect_from_server(self):
        if self.__is_connected():
            self.__safe_unregister_and_close(self.__server_to_client_sock)
            self.__server_to_client_sock = None
            print("[Info]: Disconnected from server")
        else:
            print("[Error]: Client is not connected to server")

    def __handle_sent_msg(self, msg : str, failure : bool):
        match msg.split():
            case [protocol.CLIENT_DSC_MSG]:
                self.__disconnect_from_server()
            case [protocol.CONSOLE_DSC_MSG]:
                self.__disconnect_console()
            case ["register", login, password]:
                pass
            case ["login", login, password]:
                pass
            case ["create"]:
                pass
            case ["join", game_id, game_password, color]:
                if (args := utility.silent_convert((game_id, int))) is not None and not failure:
                    color = "b" if color.lower() != "w" else "w"
                    self.__active_game_id, *_ = args
                    self.__current_color = (color == "b")
                    print(f"joined game with id {self.__active_game_id}")
            
            case ["vote", game_id, move]:
                pass

            case ["analyze", game_id]:
                pass

            case _:
                pass

    def __safe_unregister_and_close(self, sock : socket.socket|None):
        if self.__sel is not None and sock is not None:
            self.__sel.unregister(sock)
            sock.close()

    def close_app(self):
        if self.__sel is not None:
            print("[Info]: Closing client")
            self.__running = False
            self.__safe_unregister_and_close(self.__console_listener)
            self.__console_listener = None
            self.__safe_unregister_and_close(self.__console_to_client_sock)
            self.__console_to_client_sock = None

            self.__safe_unregister_and_close(self.__server_to_client_sock)
            self.__server_to_client_sock = None

            self.__sel.close()
            self.__sel = None



if __name__ == "__main__":

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <console_port> \n e.g. {sys.argv[0]} 5051")
        sys.exit(1)
    app = ChessApp("127.0.0.1", int(sys.argv[1]))
    try:
        
        app.start()
    except Exception as e:
        print(f"[Exception]: {e}")
    finally:
        app.close_app()