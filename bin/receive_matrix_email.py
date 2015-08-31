"""Receive quotes from suppliers' "matrix" spreadsheets in email attachments.
Pipe an email into stdin to process it.
"""
import logging
from sys import stdin
import traceback
from brokerage.quote_email_processor import QuoteEmailProcessor, LOG_NAME
from brokerage.quote_email_processor import CLASSES_FOR_SUPPLIERS, QuoteDAO
from core import initialize
from core.model import AltitudeSession, Session

if __name__ == '__main__':
    try:
        initialize()
        qep = QuoteEmailProcessor(CLASSES_FOR_SUPPLIERS, QuoteDAO())
        qep.process_email(stdin)
    except Exception as e:
        logging.error('Error when processing email:\n%s' % (
            traceback.format_exc()))
    finally:
        Session.remove()
        AltitudeSession.remove()
