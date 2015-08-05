"""Receive quotes from suppliers' "matrix" spreadsheets (files from a Dropbox
directory or email attachments).
"""
import logging
from sys import stdin
import traceback
from brokerage.quote_file_processor import QuoteEmailProcessor, LOG_NAME
from core import initialize
from core.model import AltitudeSession, Session

if __name__ == '__main__':
    logger = logging.getLogger(LOG_NAME)

    try:
        initialize()
        QuoteEmailProcessor().process_email(stdin)
    except Exception as e:
        logger.error('Error when processing email:\n%s' % (
            traceback.format_exc()))
    finally:
        Session.remove()
        AltitudeSession.remove()
