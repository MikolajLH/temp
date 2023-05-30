import datetime
from datetime import datetime

FORMAT = "%m/%d/%Y, %H:%M:%S"
SEPARATOR = ";"


class Parameters:
    def __init__(self):
        self.start_time = datetime.now()
        self.move_time = 60  # seconds

        self.anonymous = 0

    def new(self, start_time, move_time, anonymous):
        self.start_time = start_time
        self.move_time = move_time
        self.anonymous = anonymous

    def load(self, date_start,timedelta_move_time,date_last_move,anonymous):
        self.start_time = datetime.strptime(date_start, FORMAT)
        self.move_time = datetime.strptime(timedelta_move_time, FORMAT)
        self.anonymous = str(anonymous)

    def to_string(self):
        return self.start_time.strftime(FORMAT) + SEPARATOR + str(self.move_time) + SEPARATOR + \
            SEPARATOR + str(self.anonymous)

    def from_string(self, input):
        param_string = input.split(SEPARATOR)
        self.start_time = datetime.strptime(param_string[0], FORMAT)
        self.move_time = int(param_string[1])
        self.anonymous = param_string[2]


xs = Parameters()
