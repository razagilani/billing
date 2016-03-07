from datetime import datetime

from brokerage.quote_parsers.gee_gas_ny import GEEGasNYParser
from test.test_brokerage.test_quote_parsers import QuoteParserTest
from test.testing_utils import TestCase

class GeeGasNYTest(QuoteParserTest, TestCase):
    FILE_NAME = 'NY Rack Rates_2.2.2016.pdf'
    ALIASES = [
        'NGW Non-Heat SC2-1',
        'Con Edison-Heating-SC1'
    ]
    PARSER_CLASS = GEEGasNYParser
    EXPECTED_COUNT = 260

    def test_gee_gas_ny(self):
        q = self.quotes[0]
        self.assertEqual(datetime(2016, 2, 1), q.start_from)
        self.assertEqual(datetime(2016, 3, 1), q.start_until)
        self.assertEqual(6, q.term_months)
        self.assertEqual(datetime(2016, 2, 2), q.valid_from)
        self.assertEqual(datetime(2016, 2, 3), q.valid_until)
        self.assertEqual(None, q.min_volume)
        self.assertEqual(None, q.limit_volume)
        self.assertEqual(self.ALIASES[0], q.rate_class_alias)
        self.assertEqual(1, q.rate_class_id)
        self.assertEqual(.3732, q.price)

        # first "sweet spot" quote (last in first row)
        q = self.quotes[4]
        self.assertEqual(datetime(2016, 2, 1), q.start_from)
        self.assertEqual(datetime(2016, 3, 1), q.start_until)
        self.assertEqual(9, q.term_months)
        self.assertEqual(datetime(2016, 2, 2), q.valid_from)
        self.assertEqual(datetime(2016, 2, 3), q.valid_until)
        self.assertEqual(None, q.min_volume)
        self.assertEqual(None, q.limit_volume)
        self.assertEqual(self.ALIASES[0], q.rate_class_alias)
        self.assertEqual(.3688, q.price)

        q = self.quotes[-1]
        self.assertEqual(datetime(2016, 5, 1), q.start_from)
        self.assertEqual(datetime(2016, 6, 1), q.start_until)
        self.assertEqual(11, q.term_months)
        self.assertEqual(datetime(2016, 2, 2), q.valid_from)
        self.assertEqual(datetime(2016, 2, 3), q.valid_until)
        self.assertEqual(None, q.min_volume)
        self.assertEqual(None, q.limit_volume)
        self.assertEqual(.4673, q.price)
