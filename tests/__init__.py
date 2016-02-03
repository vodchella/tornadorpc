""" The TornadoRPC tests """

import sys
from os import path
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))


from threading import Thread
from tornadorpc import start_server
import time


def start_server(handler, port):
    """ Starts a background server thread """
    thread = Thread(target=start_server, args=[handler,], kwargs={'port':port})
    thread.daemon = True
    thread.start()
    # time to start server
    time.sleep(2)
