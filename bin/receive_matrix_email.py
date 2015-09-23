#!/usr/bin/env python
"""Receive quotes from suppliers' "matrix" spreadsheets in email attachments.
Pipe an email into stdin to process it.
"""
import logging
from sys import stdin
import traceback

from brokerage.quote_email_processor import QuoteEmailProcessor, QuoteDAO, \
    LOG_NAME
from brokerage.quote_parsers import CLASSES_FOR_SUPPLIERS
from core import initialize
from core.model import AltitudeSession, Session

if __name__ == '__main__':
    try:
        initialize()
        qep = QuoteEmailProcessor(CLASSES_FOR_SUPPLIERS, QuoteDAO())
        qep.process_email(stdin)
    except Exception as e:
        logger = logging.getLogger(LOG_NAME)
        logger.setLevel(logging.DEBUG)
        logger.error('Error when processing email:\n%s' % (
            traceback.format_exc()))
        # it is important to exit with non-0 status when an error happened,
        # because that causes Postfix to send a bounce email with the error
        # message
        raise
    finally:
        Session.remove()
        AltitudeSession.remove()
