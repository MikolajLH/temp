import os
import sys
import inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

import protocol
import utility
import socket
import sys
import os


class Console:

    CONSOLE_PREFIX : str = "[CONSOLE]>>"
    CLIENT_PREFIX : str = "[CLIENT]>>"
    SERVER_PREFIX : str = "[SERVER]>>"

    def __init__(self):
        self.__running = False
        self.__sock : socket.socket|None = None
        self.__prefix : str = Console.CONSOLE_PREFIX

    def run(self):
        self.__running = True
        while self.__running:
            msg = input(self.__prefix)
            if self.__prefix == Console.CONSOLE_PREFIX:
                self.__handle_console_msg(msg)
            elif self.__is_attached():
                msg = self.__preprocess_msg(msg)
                if (sent_successfully := protocol.send_msg(self.__sock, msg)):
                    self.__handle_sent_msg(msg)
                else:
                    print("[Error]: Couldn't send message")
                    self.__detach()


    
    def __handle_console_msg(self, msg : str):
        match msg.strip().split():
            case ["sys", *args] if len(args) > 0:
                os.system(" ".join(args))
            case ["exit"]:
                self.exit_console()
            case ["attach", host, port]:
                if(args := utility.silent_convert((host, str), (port, int))) is not None:
                    self.__attach(*args)
                else:
                    print("[Info]: Usage: attach <host : str> <port : int>")
            case []:
                pass
            case _:
                print("[Error]: Command not recognized")

    def __attach(self, host : str, port : int):
        try:
            self.__sock = protocol.create_socket()
            self.__sock.connect((host, port))

            if (ID := protocol.recv_byte(self.__sock)) is None:
                print("[Error]: couldn't receive ID from host")
                self.__detach()
            else:
                if ID == protocol.CLIENT_ID:
                    self.__prefix = Console.CLIENT_PREFIX
                    print("[Info]: Attached to client")
                elif ID == protocol.SERVER_ID:
                    self.__prefix = Console.SERVER_PREFIX
                    print("[Info]: Attached to server")
                else:
                    print("[Error]: Unknown ID")
                    self.__detach()

        except Exception as e:
            print(f"[Exception] __attach(): {e}")
            self.__sock.close()
            self.__sock = None
            

    def __is_attached(self) -> bool:
        return self.__sock is not None

    def __detach(self):
        if self.__is_attached():
            self.__prefix = Console.CONSOLE_PREFIX
            self.__sock.close()
            self.__sock = None
            print("[Info]: Console detached")

    def exit_console(self):
        if self.__running:
            print("[Info]: exiting")
            self.__detach()
            self.__running = False
            print("[Info]: Console exited")

    def __preprocess_msg(self, msg : str) -> str:
        match msg:
            case _:
                return msg
    
    def __handle_sent_msg(self, msg : str):
        match msg.split():
            case [protocol.CONSOLE_DSC_MSG | protocol.SHUTDOWN_MSG]:
                self.__detach()





if __name__ == "__main__":

    console = Console()
    try:
        console.run()
    except:
        pass