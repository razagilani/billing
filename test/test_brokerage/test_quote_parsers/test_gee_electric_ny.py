from datetime import datetime

from brokerage.quote_parsers import GEEMatrixParser
from test.test_brokerage.test_quote_parsers import QuoteParserTest
from test.testing_utils import TestCase


class TestGeeElectricNY(QuoteParserTest, TestCase):

    # these variables are accessed in QuoteParserTest.setUp
    FILE_NAME = 'GEE Rack Rate_NY_12.1.2015.xlsx'
    ALIASES = ['GEE-electric-ConEd-J-SC-02']
    PARSER_CLASS = GEEMatrixParser
    EXPECTED_COUNT = 149

    def test_first(self):
        q = self.quotes[0]
        self.assertEqual(datetime(2015, 12, 1), q.valid_from)
        self.assertEqual(datetime(2015, 12, 2), q.valid_until)
        self.assertEqual(datetime(2015, 12, 1), q.start_from)
        self.assertEqual(datetime(2016, 1, 1), q.start_until)
        self.assertEqual('GEE-electric-ConEd-J-SC-02', q.rate_class_alias)
        self.assertEqual(1, q.rate_class_id)
        self.assertEqual(6, q.term_months)
        self.assertEqual(0, q.min_volume)
        self.assertEqual(499999, q.limit_volume)
        self.assertEqual(0.08381, q.price)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual('electric', q.service_type)

    def test_last(self):
        q = self.quotes[-1]
        self.assertEqual(datetime(2015, 12, 1), q.valid_from)
        self.assertEqual(datetime(2015, 12, 2), q.valid_until)
        self.assertEqual(datetime(2016, 5, 1), q.start_from)
        self.assertEqual(datetime(2016, 6, 1), q.start_until)
        self.assertEqual(24, q.term_months)
        self.assertEqual(500000, q.min_volume)
        self.assertEqual(999999, q.limit_volume)
        self.assertAlmostEqual(0.07573, q.price, delta=0.000001)
