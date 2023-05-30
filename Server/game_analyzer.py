import chess
import chess.engine
import json
from math import exp

STOCKFISH_PATH = "stockfish/stockfish_15.1_win_x64/stockfish-windows-2022-x86-64.exe"

# path to stockfish

analysis_path = "data/analysis/"
MATE_EVAL = 1000

class ChessAnalyzer:

    def __init__(self):
        self.board = None
        self.move_stack = []
        self.best_line_stack = []
        self.alternatives = []
        self.eval_stack = []
        self.length = 0
        self.last_analyzed = 0
        self.engine = None

    def init_from_file(self, filename):
        """
        :param filename: local file name for example 'tmp'
        :return:
        """
        f = open(analysis_path + filename + '.json')
        data = json.load(f)
        self.move_stack = data['data'][0].get('move_stack')
        self.eval_stack = data['data'][0].get('eval_stack')
        self.best_line_stack = data['data'][0].get('best_line_stack')
        self.alternatives = data['data'][0].get('alternatives')
        self.length = len(self.move_stack)
        self.last_analyzed = self.length - 1

    def init(self, move_stack):
        """
        :param move_stack: move_stack of the game to analyze
        :return:
        """
        self.board = chess.Board(chess.STARTING_FEN)
        self.move_stack = list(map( str,move_stack))
        self.length = len(move_stack)
        self.best_line_stack = [None] * self.length
        self.alternatives = [None] * self.length
        self.eval_stack = [None] * self.length
        self.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    def analyze(self, time):
        """
        :param time: time spent analyzing every move
        :return:
        """
        for i in range(self.last_analyzed, self.length):
            move = self.move_stack[i]

            info = self.engine.analyse(self.board, chess.engine.Limit(time=time) , multipv=50)
            #print(info)
            alternative_moves = {}
            for line in info:
                evaluation = str(line['score'].pov(chess.WHITE))
                if evaluation[0] == '#':
                    evaluation = MATE_EVAL
                else:
                    evaluation = int(evaluation)

                alternative_moves.update({str(line['pv'][0]): evaluation})
            info = info[0]

            self.eval_stack[i] = info["score"].pov(chess.WHITE)
            self.best_line_stack[i] = info["pv"]
            self.alternatives[i] = alternative_moves
            self.board.push_san(move)
            self.last_analyzed = i
        self.fix_encoding()

    def fix_encoding(self):
        evaluation = [str(self.eval_stack[i]) for i in range(self.length)]
        for i in range(self.length):
            if evaluation[i][0] == '#':
                evaluation[i] = MATE_EVAL
            else:
                evaluation[i] = int(evaluation[i])
        for i in range(self.length):
            self.eval_stack[i] = evaluation[i]
        for i in range(self.length):
            for j in range(len(self.best_line_stack[i])):
                self.best_line_stack[i][j] = str(self.best_line_stack[i][j])

    def centi_pawn_loss(self, color):
        """
        :param color: chess.WHITE or chess.BLACK = 1 or 0
        :return: average_pawn_loss per move of the game
        """
        s = 0

        for i in range((color + 1) % 2, self.length - 1, 2):
            if self.eval_stack[i] == 0:
                s = s + self.eval_stack[i] - self.eval_stack[i + 1]
            else:
                s = (s + self.eval_stack[i] - self.eval_stack[i + 1])
        return s / (self.length // 2 + (color * self.length % 2))

    def average_centi_pawn_loss(self, color, move_stack):
        """
        :param color: chess.WHITE or chess.BLACK = 1 or 0
        :param move_stack: move_stack
        :return: average_centi_pawn_loss of player
        """
        sum_gain = 0
        player_moves = (self.length // 2 + (color * self.length % 2))
        move_stack_index = 0

        for i in range((color + 1) % 2, self.length, 2):
            player_move = self.alternatives[i].get(move_stack[move_stack_index])
            if player_move is not None:
                sum_gain += self.eval_stack[i] - player_move
            move_stack_index += 1
        return sum_gain / player_moves * (2 * color - 1)

    def average_accuracy(self, color, move_stack):
        """
        :param color: chess.WHITE or chess.BLACK = 1 or 0
        :param move_stack: move_stack
        :return: average accuracy of player based on https://lichess.org/page/accuracy
        """
        def win_chance(centipawns):
            return 50 + 50 * (2 / (1 + exp(-0.00368208 * centipawns)) - 1)

        def accuracy(win_before, win_after):

            return 103.1668 * exp(-0.04354 * (win_before - win_after)) - 3.1669

        acc_sum = 0
        move_stack_index = 0
        player_moves = (self.length // 2 + (color * self.length % 2))
        for i in range((color + 1) % 2, self.length, 2):
            player_move = self.alternatives[i].get(move_stack[move_stack_index])
            if player_move is not None:
                if color == chess.WHITE:
                    acc_sum += accuracy(win_chance(self.eval_stack[i]), win_chance(player_move)) * (2 * color - 1)
                else:
                    acc_sum += accuracy(win_chance(player_move), win_chance(self.eval_stack[i]))
            move_stack_index += 1
        return acc_sum / player_moves

    def accuracy(self, color, move_stack):
        """
        :param color: chess.WHITE or chess.BLACK = 1 or 0
        :param move_stack: move_stack
        :return: tuple: (accuracy with respect to general move, accuracy with respect to engine )
        """
        game_counter = 0
        eval_counter = 0

        len = (self.length // 2 + (color * self.length % 2))
        player_moves = (self.length // 2 + (color * self.length % 2))

        for i in range((color + 1) % 2, self.length, 2):

            if self.move_stack[i] == move_stack[i // 2]:
                game_counter = game_counter + 1
            if self.best_line_stack[i][0] == move_stack[i // 2]:
                eval_counter = eval_counter + 1
        return game_counter / player_moves, eval_counter / player_moves

    def evaluation(self, nth):
        """
        :param nth: nth move of the game
        :return: evaluation before nth move of the game, evaluation(0) is eval of starting position
        """
        if nth >= self.length:
            return None
        return self.eval_stack[nth]

    def save_to_file(self, path):
        """
        :param path: local file name for example 'tmp'
        :return:
        """
        if self.last_analyzed + 1 != self.length:
            raise Exception("analysis not completed - cannot be saved")

        data = {'data': [
            {'move_stack': self.move_stack, 'eval_stack': self.eval_stack,
             'best_line_stack': self.best_line_stack, 'alternatives': self.alternatives}]}
        with open(analysis_path + path + '.json', 'w') as outfile:
            json.dump(data, outfile)
        outfile.close()

    def quit(self):
        self.engine.close()


def test():
    move_stack = ["e2e4", "e7e5", "f1c4", "d7d6", "d1h5", "g8f6", "h5f7"]
    '''
    move_stack = ["d2d4", "g8f6", "g1f3", "e7e6", "c1f4", "c7c5", "e2e3", "d8b6", "b1c3", "c5d4", "e3d4", "b6b2",
                  "c3b5", "f8b4", "f3d2", "f6d5", "a1b1", "b2a2", "b1b4", "d5b4", "b5d6", "e8e7", "f1c4", "b4c2",
                  "e1f1", "a2a1", "d1a1", "c2a1", "f1e2", "a1c2", "d4d5", "b8a6", "h1c1", "a6b4", "d2f3", "b7b6",
                  "c4b3", "c8a6", "e2d2", "b4d3"]
                  '''
    Analyze = ChessAnalyzer()
    Analyze.init(move_stack)
    Analyze.analyze(0.1)
    print(Analyze.centi_pawn_loss(chess.WHITE))
    print(Analyze.centi_pawn_loss(chess.BLACK))
    print(Analyze.accuracy(chess.WHITE, ["e2e4", "f1c4", "d1h5", "h5f7"]))
    print(Analyze.accuracy(chess.BLACK, ["e7e5", "d7d6", "g8f6"]))
    print(Analyze.accuracy(chess.BLACK, ["c7c5", "d7d6", "g7g6"]))
    print(Analyze.accuracy(chess.BLACK, ["c7c5", None, "g7g6"]))
    Analyze.save_to_file("tmp")

    Analyze2 = ChessAnalyzer()
    Analyze2.init_from_file("tmp")
    print(Analyze2.centi_pawn_loss(chess.WHITE))
    print(Analyze.accuracy(chess.BLACK, ["c7c5", None, "g7g6"]))
    print(Analyze.average_centi_pawn_loss(chess.WHITE, ["e2e4", "f1c4", "d1h5", "h5f7"]))
    print(Analyze.average_centi_pawn_loss(chess.BLACK, ["c7c5", None, "g7g6"]))
    Analyze.quit()


if __name__ == '__main__':
    test()
