#!/usr/bin/env python
"""Receive quotes from suppliers' "matrix" spreadsheets in email attachments.
Pipe an email into stdin to process it.
"""
import logging
from sys import stdin
import traceback

import statsd
from boto.s3.connection import S3Connection

from brokerage.quote_email_processor import QuoteEmailProcessor, QuoteDAO, \
    LOG_NAME
from brokerage.quote_parsers import CLASSES_FOR_FORMATS
from core import initialize
from core.model import AltitudeSession, Session


if __name__ == '__main__':
    try:
        initialize()
        from core import config
        s3_connection = S3Connection(
            config.get('aws_s3', 'aws_access_key_id'),
            config.get('aws_s3', 'aws_secret_access_key'),
            is_secure=config.get('aws_s3', 'is_secure'),
            port=config.get('aws_s3', 'port'),
            host=config.get('aws_s3', 'host'),
            calling_format=config.get('aws_s3', 'calling_format'))
        s3_bucket_name = config.get('brokerage', 'quote_file_bucket')
        qep = QuoteEmailProcessor(CLASSES_FOR_FORMATS, QuoteDAO(),
                                  s3_connection, s3_bucket_name)
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
