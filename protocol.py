import socket
import utility


FORMAT = 'utf-8'
HEADER_SIZE = 128
TIMEOUT = 0.5

SERVER_ID = b"\x02"
CLIENT_ID = b"\x04"

CONFIRMATION_BYTE = b"\xff"
FAILURE_BYTE = b"\xee"


FEN_PREFIX = "[]"
CONSOLE_DSC_MSG = "<>"
CLIENT_DSC_MSG = "><"
SHUTDOWN_MSG = "exit"


def send_byte(sock : socket.socket, byte : bytes, verbose : bool = True) -> bool:
    """
    Tries to send single byte using provided socket,
    returns False if any exception has occured;
    if verbose is True, will print what type of exception has occured
    """
    assert len(byte) == 1
    sent = 0
    try:
        sent = sock.send(byte)
    except Exception as e:
        if verbose:
            print(f"[Exception] send_byte(): {e}")
    finally:
        return sent != 0




def recv_byte(sock : socket.socket, verbose : bool = True) -> bytes|None:
    """
    Tries to receive single byte using provided socket,
    returns the byte received or None if any exception has occured;
    if verbose is True, will print what type of exception has occured
    """
    byte = None
    try:
        rcv = sock.recv(1)
        byte = None if rcv == b'' else rcv
    except Exception as e:
        if verbose:
            print(f"[Exception] recv_byte(): {e}")
    finally:
        return byte



def send_msg(sock : socket.socket, msg : str, verbose : bool = True) -> bool:
    """
    Tries to send string message using provided socket,
    returns False if any exception has occured;
    if verbose is True, will print what type of exception has occured
    """
    try:
        bmsg = msg.encode(FORMAT)
        bmsg_length = len(bmsg)
        bheader = str(bmsg_length).encode(FORMAT)
        bheader += b' ' * (HEADER_SIZE - len(bheader))

        sent = 0
        while bheader:
            sent = sock.send(bheader)
            if sent == 0:
                return False
            bheader = bheader[sent:]
        while bmsg:
            sent = sock.send(bmsg)
            if sent == 0:
                return False
            bmsg = bmsg[sent:]
        return True
    except Exception as e:
        if verbose:
            print(f"[Exception] send_msg(): {e}")
        return False
        



def recv_msg(sock : socket.socket, verbose : bool = True) -> str|None:
    """
    Tries to receive string message using provided socket,
    returns message received or None if any exception has occured;
    if verbose is True, will print what type of exception has occured
    """
    try:
        msg = None
        bheader = b''
        while len(bheader) != HEADER_SIZE:
            recv = sock.recv(HEADER_SIZE - len(bheader))
            if recv == b'':
                return None
            bheader += recv
        
        bmsg_length = int(bheader.decode(FORMAT))
        bmsg = b''
        while len(bmsg) != bmsg_length:
            recv = sock.recv(bmsg_length - len(bmsg))
            if recv == b'':
                return None
            bmsg += recv
        msg = bmsg.decode(FORMAT)
        return msg
    
    except Exception as e:
        if verbose:
            print(f"[Exception] recv_msg(): {e}")
        return None


def create_listening_socket(host : str, port : int, verbose : bool = True) -> socket.socket|None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        sock.bind((host,port))
        sock.listen()
        return sock
    except Exception as e:
        if verbose:
            print(f"[Exception] create_listening_socket(): {e}")
        return None


def create_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)
    return sock



if __name__ == "__main__":
    pass