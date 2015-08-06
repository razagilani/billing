"""Receive quotes from suppliers' "matrix" spreadsheets (files from a Dropbox
directory or email attachments).
"""
import logging
from fcntl import flock, LOCK_EX, LOCK_NB
from sys import stdin
import traceback
from brokerage.quote_email_processor import QuoteEmailProcessor, LOG_NAME
from brokerage.quote_email_processor import CLASSES_FOR_SUPPLIERS, QuoteDAO
from core import initialize
from core.model import AltitudeSession, Session

if __name__ == '__main__':
    # prevent multiple instances from running at once
    try:
        f = open(__file__)
        flock(f, LOCK_EX | LOCK_NB)
    except IOError:
        exit(1)

    try:
        initialize()
        qep = QuoteEmailProcessor(CLASSES_FOR_SUPPLIERS, QuoteDAO())
        qep.process_email(stdin)
    except Exception as e:
        logger.error('Error when processing email:\n%s' % (
            traceback.format_exc()))
    finally:
        Session.remove()
        AltitudeSession.remove()
