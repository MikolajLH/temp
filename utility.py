from typing import List, Any, Tuple
from collections.abc import Callable


From, To = Any, Any

def silent_apply(arg : From, fn : Callable[[From], To]) -> To|None:
    """
    tries to apply fn to arg,
    if the function throws, returns None
    else returns fn(arg)
    """
    try:
        return fn(arg)
    except:
        return None
    

def silent_convert(*args : Tuple[Any, Callable[[Any], Any]]) -> List[Any]|None:
    """
    tries to each function to it's corresponding args,
    in casy any of the function throwes returns None
    else returns list of results
    """
    res = []
    for arg, fn in args:
        try:
            res += [fn(arg)]
        except:
            return None
    return res

    
    
def safe_apply(arg : From|None, fn : Callable[[From], To]) -> To|None:
    """
    if arg is None returns None
    else returns fn(arg)
    """
    if arg is None:
        return None
    return fn(arg)

def safe_silent_apply(arg : From|None, fn : Callable[[From], To]) -> To|None:
    """Composition of safe_apply and silent_apply"""
    if arg is None:
        return None
    try:
        return fn(arg)
    except:
        return None


if __name__ == "__main__":
    pass

