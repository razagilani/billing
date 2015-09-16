"""Receive quotes from suppliers' "matrix" spreadsheets in a local directory.
"""
from fcntl import flock, LOCK_EX, LOCK_NB
from core import initialize
from brokerage.quote_file_processor import QuoteFileProcessor

if __name__ == '__main__':
    # prevent multiple instances from running at once
    try:
        f = open(__file__)
        flock(f, LOCK_EX | LOCK_NB)
    except IOError:
        exit(1)

    initialize()
    QuoteFileProcessor().run()
