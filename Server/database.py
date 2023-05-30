import os.path
import csv

FORMAT = "%m/%d/%Y, %H:%M:%S"
SEPARATOR = ";"


class Database:
    def __init__(self, path,filename):
        self.path = path
        self.labels = []
        self.filename = filename

    def read_first_row(self):
        with open(self.path + self.filename, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=';', quotechar='|')
            data = []
            for row in reader:
                data.append(row)
                return data

    def read(self):

        with open(self.path + self.filename, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=';', quotechar='|')
            data = []
            for row in reader:
                data.append(row)
        return data

    def write_labels(self, labels, data,option='w'):
        with open(self.path + self.filename, option, newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter= SEPARATOR,
                                    quotechar='\"', quoting=csv.QUOTE_MINIMAL)
            if labels:
                writer.writerow(labels)
            for d in data:
                writer.writerow(d)

    def exists(self):
        return os.path.isfile(self.path + self.filename)


def test():
    db = Database("data/","test.csv")
    db.write_labels(["l1","l2"],[['Spam', 'Lovely Spam', 'Wonderful Spam'],['Spam', 'Lovely Spam', 'Wonderful Spam']])
    db.write_labels([],[['Spam', 'Lovely Spam', 'Wonderful Spam']],'a')
    print(db.read())


if __name__ == '__main__':
    test()

