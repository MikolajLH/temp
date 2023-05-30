
import database


class Voter:
    def __init__(self):
        self.vote_counter = dict()

    def new(self, move_list):
        self.vote_counter = dict()

        for move in move_list:
            self.vote_counter.update({move: 0})

    def vote(self, vote):

        self.vote_counter.update({vote: self.vote_counter.get(vote) + 1})

    def votes(self):
        return self.vote_counter

    def get_most_vote(self):
        return [key for key, value in self.vote_counter.items() if value == max(self.vote_counter.values())]

