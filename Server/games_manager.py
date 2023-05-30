from queue import PriorityQueue
from time import sleep
import chess
import chess.pgn
import json

import Parameters
import game
import datetime
import game_analyzer
from datetime import datetime

import database
import account_manager
import voting_system

FORMAT = "%m/%d/%Y, %H:%M:%S"
SEPARATOR = ";"
PATH = "data/"

NO_GAME_IN_QUEUE = -1


class GameManager:
    def __init__(self):
        self.queue = PriorityQueue()
        self.games = {}
        self.votes_archive = {}
        self.new_id = 1
        self.ongoing_games_db = database.Database("data/", "ongoing_games.csv")
        self.game_id_db = database.Database("data/", "ids.csv")
        self.finished_games_db = database.Database("data/", "finished.csv")


    def new_game(self, creator, password, parameters=None):
        """
        create new game, returns game_id of the created game
        """
        if parameters is None:
            parameters = Parameters.Parameters()
            parameters.new(datetime.now(), 1, True)

        new_game = game.Game(self.new_id, parameters, creator, password)
        new_vote = voting_system.Voter()
        new_vote.new(new_game.get_legal_moves_uci())
        self.votes_archive.update({self.new_id: []})
        self.games.update({self.new_id: (new_game, new_vote)})
        self.queue.put((new_game.make_int(), self.new_id))
        self.new_id += 1
        Data_id = [[self.new_id]]
        self.game_id_db.write_labels(["next_game_will_have_id"], Data_id)
        return self.new_id - 1

    def process(self):
        """
        process 1 game
        returns game that was processed
        returns NO_GAME_IN_QUEUE if there are no games running
        """

        now = datetime.now()
        # print(self.games)
        if self.games == {}:
            return NO_GAME_IN_QUEUE
        p, game_id = self.queue.get()
        if game_id is None:
            return NO_GAME_IN_QUEUE
        tmp = self.games.get(game_id)
        if tmp is None:  # there are no games active as of this moment
            return NO_GAME_IN_QUEUE
        act_game, votes = tmp

        if now.timestamp() < p:
            print("PROCESSING - NOT YET ", now.timestamp(), p, act_game.get_fen())
            self.queue.put((p, game_id))
            return -1
        print("NOW PROCESSING ", p, act_game.get_fen())
        # ... 'count' votes and make a move
        counted_votes = votes.get_most_vote()
        if len(counted_votes) == 1:  # exists exactly 1 vote with max. no votes (no tie)
            act_game.make_move(counted_votes[0])
            # print(act_game.get_state())
            votes_dict = votes.votes()
            vote_hist = self.votes_archive.get(game_id)
            vote_hist.append(votes_dict)
            self.votes_archive.update({game_id: vote_hist})
            if act_game.get_state() != '*':  # game ends
                act_game.last_move_time = datetime.now()

                #  ... save result to file
                self.finished_games_db.write_labels([], [[game_id]], "a+")
                self.save_to_pgn(game_id)
                self.games.pop(game_id)

                return game_id

            votes.new(act_game.get_legal_moves_uci())
        #else:
            #raise Exception("tie")


        act_game.last_move_time = datetime.now()
        self.queue.put((act_game.make_int(), game_id))
        return game_id

    def process_all(self):
        """
        process games while there exist games to be processed
        returns list of games that have been processed
        returns NO_GAME_IN_QUEUE if there are no games running
        """

        res_t = []
        res = 0
        while res != -1:
            res = self.process()
            if res != -1:
                res_t.append(res)
        return res_t

    def load(self):
        """
        load games from ongoing_games file
        """
        d = self.ongoing_games_db.read()
        for k in d[1:]:
            self.load_game(int(k[0]))

        self.new_id = int(self.game_id_db.read()[1][0])

    def save(self):
        """
        saves file ongoing_games.csv
        """
        Data = [0 for i in range(len(self.games))]
        i = 0
        for G, V in self.games.values():
            Data[i] = [G.game_id]

        self.ongoing_games_db.write_labels(["game_id"], Data)

    def vote(self, game_id, color, vote, AM):
        """
        :param game_id:
        :param color:  1 - white; 0 black
        :param vote: move in format 'e2e4'
        :param AM: account_manager object
        :return:
        """
        if not AM.vote_permission(game_id, color):
            raise Exception("user can't vote - wrong color/no permission")

        g, v = self.games.get(game_id)
        v.vote(vote)

        AM.vote(game_id, g.move_number(), vote)

    def user_active_games(self, AM):
        """
        :param AM: account_manager object
        :return: set
        """
        user_games_set = AM.user_games()
        active_games = self.games.keys()
        return user_games_set & active_games  # intersection

    def user_past_games(self, AM):
        """
        :param AM: account_manager object
        :return: set
        """
        user_games_set = AM.user_games()
        active_games = self.games.keys()
        return user_games_set - active_games

    def get_game(self, game_id):
        G, V = self.games.get(game_id)
        return G

    def join_game(self, game_id, color, password, AM):
        """
        :param game_id: game_id int
        :param color: 'w' or 'b'
        :param password: password string
        :param AM: account_manager object
        """
        G, V = self.games.get(game_id)
        if G.password != password:
            raise Exception("Wrong password")
        AM.join_game(game_id, color)
        G.new_player(AM.login, color)

    def save_to_pgn(self, game_id):
        pgn_game = chess.pgn.Game()
        G, V = self.games.get(game_id)
        pgn_game.headers["Event"] = "MultiChess"
        pgn_game.headers["Date"] = G.get_start_time()
        pgn_game.headers["Site"] = "MultiChess"
        pgn_game.headers["White"] = str(list(G.white))
        pgn_game.headers["Black"] = str(list(G.black))
        pgn_game.headers["Result"] = G.get_state()
        pgn_game.headers["Game_Parameters"] = G.save()
        vote_hist = self.votes_archive.get(game_id)
        for i in range(len(vote_hist)):
            pgn_game.headers[f"Votes_move_{i + 1}"] = vote_hist[i]
        node = pgn_game.add_variation(G.board.move_stack[0])
        for move in G.board.move_stack[1:len(G.board.move_stack)]:
            node = node.add_variation(move)

        print(pgn_game, file=open("data/pgn/" + str(game_id) + ".pgn", "w"), end="\n\n")

    def load_game(self, game_id):
        pgn = open(f"data/pgn/{game_id}.pgn")
        chess_game = chess.pgn.read_game(pgn)
        dictionary_white = chess_game.headers["White"]
        dictionary_black = chess_game.headers["Black"]

        if dictionary_white:
            white = json.loads(str(dictionary_white).replace('\'', '"'))
        else:
            white = dict()

        if dictionary_black:
            black = json.loads(str(dictionary_black).replace('\'', '"'))
        else:
            black = dict()

        game_params = chess_game.headers["Game_Parameters"]
        if game_params:
            dictionary_game = json.loads(str(game_params).replace('\'', '"'))
        else:
            dictionary_game = dict()

        P = Parameters.Parameters()
        P.from_string(dictionary_game.get('parameters'))
        G = game.Game(game_id, P, dictionary_game.get('creator'), dictionary_game.get('password'),
                      last_move=datetime.strptime(dictionary_game.get('last_move'), FORMAT))
        G.load(white, black)
        for move in chess_game.mainline_moves():
            G.make_move_push(move)
        self.queue.put((G.make_int(), game_id))
        new_vote = voting_system.Voter()
        new_vote.new(G.get_legal_moves_uci())
        self.games.update({game_id: (G, new_vote)})
        vote_hist = [None] * len(G.board.move_stack)
        for i in range(len(G.board.move_stack)):
            vote_hist[i] = chess_game.headers[f"Votes_move_{i + 1}"]
        self.votes_archive.update({game_id: vote_hist})

    def exit(self):
        """
        edits ongoing_games.csv file
        saves unfinished games
        """
        self.save()
        for game_id in self.games.keys():
            self.save_to_pgn(game_id)

    def get_all_votes(self, game_id):
        G, V = self.games.get(game_id)
        return V.votes

    def analyze(self, game_id, time):
        """

        :param game_id:
        :param time: time spent for one move
        :return:
        """
        self.load_game(game_id)
        G, V = self.games.get(game_id)
        print(G.board)
        Analyze = game_analyzer.ChessAnalyzer()
        Analyze.init(G.board.move_stack)
        Analyze.analyze(time)
        Analyze.save_to_file(str(game_id))
        Analyze.quit()

    def get_analysis_result(self, game_id, AM):
        """

        :param game_id:
        :param AM: account_manager object
        :return: tuple:  (accuracy with respect to general move, accuracy with respect to engine,
                average_centi_pawn_loss, average_accuracy)
        """
        C, dictionary = AM.games.get(game_id)

        Analyze = game_analyzer.ChessAnalyzer()
        Analyze.init_from_file(str(game_id))
        if C == 'w':
            color = 1
        else:
            color = 0
        move_stack = []
        for i in range((color + 1) % 2, Analyze.length, 2):
            move_stack.append(dictionary.get(str(i)))
        res = Analyze.accuracy(color, move_stack)

        return *res, Analyze.average_centi_pawn_loss(color, move_stack), Analyze.average_accuracy(color,move_stack)


    def next_move_datetime(self, game_id):
        G, V = self.games.get(game_id)
        return G.next_move_datetime()


def test():
    GM = GameManager()
    GM.load()
    game_id = GM.new_game(0, "")
    print(GM.process())
    print(game_id)
    sleep(1)
    print(GM.process())
    print(GM.process())
    sleep(1)
    print(GM.process())
    sleep(1)
    print(GM.process())
    #GM.save()



def test_game_and_account(first_run=False):
    AM = account_manager.AccountManager()
    AM1 = account_manager.AccountManager()

    if first_run:
        AM.create_account("admin", "admin")
        AM.create_account("user1", "123")
    AM.login_now("admin", "admin")
    AM1.login_now("user1", "123")

    GM = GameManager()
    GM.new_game(0, "")


def test_play(first_run=False):
    GM = GameManager()
    GM.load()
    P = Parameters.Parameters()
    P.new(datetime.now(), 1, 0)

    game_id = GM.new_game(0, "123", P)
    P1 = account_manager.AccountManager()
    P2 = account_manager.AccountManager()

    if first_run:
        P1.create_account("admin", "admin")
        P2.create_account("user1", "123")
    P1.login_now("admin", "admin")
    P2.login_now("user1", "123")
    if not first_run:
        P1.load()
        P2.load()

    GM.join_game(game_id, 'w', "123", P1)
    GM.join_game(game_id, 'b', "123", P2)

    print(GM.process_all())
    GM.vote(game_id, 1, 'e2e4', P1)
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 0, 'e7e5', P2)
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 1, 'f1c4', P1)
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 0, 'd7d6', P2)
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 1, 'd1h5', P1)
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 0, 'g8f6', P2)
    print(GM.next_move_datetime(game_id))
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 1, 'h5f7', P1)
    print(GM.get_game(game_id))
    sleep(1)
    print(GM.process_all())
    print(GM.process_all())

    P1.save()
    P2.save()
    GM.save()


def test_PGN(first_run=False):
    GM = GameManager()
    P = Parameters.Parameters()
    P.new(datetime.datetime.now(), 1, 0)

    game_id = GM.new_game(0, "123", P)
    P1 = account_manager.AccountManager()
    P2 = account_manager.AccountManager()
    # if first_run:
    #    P1.create_account("admin", "admin")
    #    P2.create_account("user1", "123")
    P1.login_now("admin", "admin")
    P2.login_now("user1", "123")

    if first_run:
        GM.join_game(game_id, 'w', "123", P1)
        GM.join_game(game_id, 'b', "123", P2)

    print(GM.user_active_games(P1))
    print(GM.user_past_games(P1))
    print(GM.process_all())
    GM.vote(game_id, 1, 'e2e4', P1)
    sleep(1)
    print(GM.process_all())
    G = GM.get_game(game_id)


def test_multiple_votes():  # provokes exception //tie
    GM = GameManager()
    P = Parameters.Parameters()
    P.new(datetime.datetime.now(), 1, 0)

    game_id = GM.new_game(0, "123", P)
    P1 = account_manager.AccountManager()
    P2 = account_manager.AccountManager()
    P1.login_now("admin", "admin")
    P2.login_now("user1", "123")
    GM.join_game(game_id, 'w', "123", P1)
    GM.join_game(game_id, 'w', "123", P2)
    GM.vote(game_id, 1, 'e2e4', P1)
    GM.vote(game_id, 1, 'd2d4', P2)
    sleep(1)
    GM.process()


def test_saving_game():
    GM = GameManager()
    GM.load()
    P = Parameters.Parameters()
    P.new(datetime.now(), 1, 0)

    game_id = GM.new_game(0, "123", P)
    P1 = account_manager.AccountManager()
    P2 = account_manager.AccountManager()

    P1.login_now("admin", "admin")
    P2.login_now("user1", "123")
    P1.load()
    P2.load()

    GM.join_game(game_id, 'w', "123", P1)
    GM.join_game(game_id, 'b', "123", P2)
    print(GM.process_all())
    GM.vote(game_id, 1, 'e2e4', P1)
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 0, 'e7e5', P2)
    sleep(1)
    print(GM.process_all())
    P1.save()
    P2.save()
    GM.exit()


def test_loading_game():
    GM = GameManager()
    GM.load()
    P1 = account_manager.AccountManager()
    P2 = account_manager.AccountManager()

    P1.login_now("admin", "admin")
    P2.login_now("user1", "123")
    P1.load()
    P2.load()
    game_id = GM.user_active_games(P1)
    print(game_id)
    game_id = game_id.pop()
    GM.vote(game_id, 1, 'f1c4', P1)
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 0, 'd7d6', P2)
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 1, 'd1h5', P1)
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 0, 'g8f6', P2)
    sleep(1)
    print(GM.process_all())
    GM.vote(game_id, 1, 'h5f7', P1)
    print(GM.get_game(game_id))
    sleep(1)
    print(GM.process_all())
    print(GM.process_all())

    P1.save()
    P2.save()
    GM.save()
    print(GM.process_all())


def analysis_test(game_id):
    GM = GameManager()
    GM.load()
    GM.analyze(game_id, 0.1)
    Analysis = game_analyzer.ChessAnalyzer()
    Analysis.init_from_file(str(game_id))
    print(Analysis.centi_pawn_loss(chess.WHITE))
    print(Analysis.centi_pawn_loss(chess.BLACK))

    P1 = account_manager.AccountManager()
    P1.login_now("admin", "admin")
    print(GM.get_analysis_result(game_id, P1))

    P2 = account_manager.AccountManager()
    P2.login_now("user1", "123")
    print(GM.get_analysis_result(game_id, P2))


if __name__ == '__main__':
    # test_game_and_account(False)  # creates usr and .csv
    # test_PGN(True)
    # test_multiple_votes()
    # test_saving_game()
    # test_loading_game()
    # test_play()  # run with True the first time to create .csv
    analysis_test(6)
    # test()
