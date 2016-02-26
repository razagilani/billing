"""This module contains tests for individual QuoteParser subclasses. Each
test is based on an example file in the "quote_files" directory.
"""
from abc import ABCMeta
from collections import defaultdict
from datetime import datetime
from os.path import join

from mock import Mock

from core import ROOT_PATH
from test.testing_utils import TestCase


class QuoteParserTestCase(TestCase):
    """Superclass that handles the shared setup code and assertions that are
    always the same in all QuoteParsers.
    """
    __metaclass__ = ABCMeta

    # don't change these in subclasses
    DIRECTORY = join(ROOT_PATH, 'test', 'test_brokerage', 'quote_files')
    RATE_CLASS_ID = 1

    # name of the example file in the above directory (set in subclass)
    FILE_NAME = None

    # QuoteParser subclass to use (set in subclass)
    PARSER_CLASS = None

    # rate class alias strings for quotes to be checked in the test (usually
    # only the first quote) (set in subclass)
    ALIASES = []

    # number of quotes that should be extracted from the file (set in subclass)
    EXPECTED_COUNT = None

    def setUp(self):
        # this mock replaces the brokerage.brokerate_model module to avoid
        # accessing the database
        dao = Mock()
        dao.load_rate_class_aliases = Mock(
            return_value=defaultdict(lambda: [self.RATE_CLASS_ID]))

        self.parser = self.PARSER_CLASS(brokerage_dao=dao)

        self.assertEqual(0, self.parser.get_count())

        with open(join(self.DIRECTORY, self.FILE_NAME), 'rb') as spreadsheet:
            self.parser.load_file(spreadsheet)
        self.parser.validate()
        self.assertEqual(0, self.parser.get_count())
        self.quotes = list(self.parser.extract_quotes())

        # TODO: maybe this code belongs in a test method rather than setUp
        self.assertEqual(self.EXPECTED_COUNT, len(self.quotes))
        self.assertEqual(self.EXPECTED_COUNT, self.parser.get_count())
        for quote in self.quotes:
            quote.validate()
            self.assertEqual(datetime.utcnow().date(),
                             quote.date_received.date())
