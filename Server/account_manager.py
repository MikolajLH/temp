import database
import hashlib
import json

SALT = "absflg"  # used for hashing passwords


class AccountManager:
    def __init__(self):
        self.login = None
        self.logged_in = False
        self.games = dict()
        self.usr = database.Database("data/", "usr.csv")

    def login_now(self, login, password):
        if self.logged_in:
            raise Exception("already logged in")
        self.login = login
        usr = database.Database("data/", login + ".csv")
        temp = usr.read_first_row()[0][0]
        salt = SALT
        dataBase_password = password + salt
        hashed = hashlib.md5(dataBase_password.encode())
        if hashed.hexdigest() == temp:
            self.logged_in = True
            self.load()
            return True
        return False

    def load(self):
        usr = database.Database("data/", self.login + ".csv")
        data = usr.read()

        for d in data[1:]:
            if d is None:
                continue
            dictionary = d[2]

            if dictionary != []:

                modified = str(dictionary).replace('\'', '"')

                votes = json.loads(str(modified))

            else:
                votes = dict()

            self.games.update({int(d[0]): (d[1], votes)})

    def save(self):
        usr = database.Database("data/", self.login + ".csv")
        temp = usr.read_first_row()[0][0]
        data = []

        for game_id, game in self.games.items():
            data.append([game_id, game[0], game[1]])

        usr.write_labels([temp], data)

    def get_color(self, game):  # returns color user plays in game
        return self.games.get(game)[0]

    def create_account(self, login, password, additional_info=None):
        if additional_info is None:
            additional_info = []
        usr = database.Database("data/", login + ".csv")
        if not usr.exists():
            salt = SALT
            dataBase_password = password + salt
            hashed = hashlib.md5(dataBase_password.encode())
            usr.write_labels([hashed.hexdigest()] + additional_info, [])
            return True
        raise Exception('login already exists ')

    def join_game(self, game_id, color):
        if not self.logged_in:
            raise Exception("Not logged in")
        if game_id in self.games.keys():
            raise Exception('already joined')
        if not (color == 'w' or color == 'b'):
            raise Exception('wrong color')
        self.games.update({game_id: (color, [])})

    def user_games(self):
        return self.games.keys()

    def vote_permission(self, game_id, color):

        if game_id not in self.games:
            return False
        usr_color, dictionary = self.games.get(game_id)

        return (usr_color == 'w' and color == 1) or (usr_color == 'b' and color == 0)

    def vote(self, game_id, move_number, move):

        color, dictionary = self.games.get(game_id)
        if dictionary == []:
            dictionary = dict()
        dictionary.update({str(move_number): move})

        self.games.update({game_id: (color, dictionary)})


def test(first_run=False):
    AM = AccountManager()

    res = AM.login_now("admin", "adnim")
    print(res)
    res = AM.login_now("admin", "admin")
    print(res)


def test2():
    AM = AccountManager()
    AM.create_account("admin", "admin")
    AM.create_account("admin", "admin")
    # should raise Exception - login already exists


if __name__ == '__main__':
    test()
    test2()
