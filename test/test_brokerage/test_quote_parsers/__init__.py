"""This module contains tests for individual QuoteParser subclasses. Each
test is based on an example file in the "quote_files" directory.
"""
from abc import ABCMeta
from collections import defaultdict
from datetime import datetime
from os.path import join

from mock import Mock

from core import ROOT_PATH

DIRECTORY = join(ROOT_PATH, 'test', 'test_brokerage', 'quote_files')

class QuoteParserTest(object):
    """Base for TestCase classes that test QuoteParsers. Subclasses should
    inherit from both this and TestCase (with TestCase second).
    """
    __metaclass__ = ABCMeta

    # QuoteParser subclass to use
    PARSER_CLASS = None

    # name of example quote file
    FILE_NAME = None

    # number of quotes extracted from the file
    EXPECTED_COUNT = None

    def setUp(self):
        """Contains assertions that should be common to all QuoteParsers,
        assumint it's OK to put assertions in the setUp method.
        """
        # this mock replaces the brokerage.brokerate_model module to avoid
        # accessing the database
        dao = Mock()
        dao.load_rate_class_aliases = Mock(
            return_value=defaultdict(lambda: [1]))

        self.parser = self.PARSER_CLASS(brokerage_dao=dao)
        self.assertEqual(0, self.parser.get_count())

        with open(join(DIRECTORY, self.FILE_NAME), 'rb') as spreadsheet:
            self.parser.load_file(spreadsheet, file_name=self.FILE_NAME)

        quote_list = list(self.parser.extract_quotes())
        self.assertEqual(self.parser.get_count(), self.EXPECTED_COUNT)
        self.assertEqual(self.EXPECTED_COUNT, len(quote_list))

        for quote in quote_list:
            quote.validate()
            self.assertEqual(datetime.utcnow().date(),
                             quote.date_received.date())
        self.quotes = quote_list
