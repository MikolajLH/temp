import datetime

import chess
import chess.pgn
import Parameters
FORMAT = "%m/%d/%Y, %H:%M:%S"


class Game:

    def __init__(self, id, parameters: Parameters.Parameters, creator=0, password="", fen=None,
                 last_move=datetime.datetime.now()):
        self.game_id = id
        self.parameters = parameters
        if fen is None:
            fen = chess.STARTING_FEN
        self.board = chess.Board(fen)
        self.creator = creator  # user_id
        self.password = password
        self.last_move_time = last_move
        self.white = set()  # user_ids
        self.black = set()  # user_ids

    def save(self):
        dictonary = {}
        dictonary.update({"creator": self.creator, "password": self.password, "last_move": self.last_move_time.strftime(FORMAT),
                          "parameters": self.parameters.to_string()})
        return dictonary

    def load(self, white, black):
        self.white = white
        self.black = black


    def new_player(self, id, side):  # True - White
        if side == 'w':
            self.white.add(id)
        else:
            self.black.add(id)

    def make_int(self):
        next_move_time = self.last_move_time + datetime.timedelta(seconds=self.parameters.move_time)
        return int(next_move_time.timestamp())

    def make_move(self, move):
        self.board.push_san(move)

    def make_move_push(self, move):
        self.board.push(move)

    def get_fen(self):
        return self.board.fen()

    def get_san(self):
        starting_board = chess.Board(chess.STARTING_FEN)
        if not self.board.move_stack:
            return ""
        return starting_board.variation_san(self.board.move_stack)

    def get_last_move(self):
        return self.board.move_stack[-1]

    def get_state(self):
        return self.board.result()

    def get_legal_moves(self):
        return self.board.legal_moves

    def get_legal_moves_uci(self):
        return list(map(chess.Move.uci, self.board.legal_moves))

    def turn(self):
        # white - True
        return self.board.turn

    def move_number(self):
        return len(self.board.move_stack)

    def get_piece(self, a, b):
        # (0, 0) is left down corner, (0,7) right down corner
        return self.board.piece_at(8 * a + b)

    def get_start_time(self):
        return self.parameters.start_time
