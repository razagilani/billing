from datetime import datetime

from brokerage.quote_parsers import DirectEnergyMatrixParser
from test.test_brokerage.test_quote_parsers import QuoteParserTestCase


class TestDirectEnergy(QuoteParserTestCase):
    FILE_NAME = 'Matrix 1 Example - Direct Energy.xls'
    ALIASES = ['Direct-electric-CT-CLP-37, R35--']
    PARSER_CLASS = DirectEnergyMatrixParser
    EXPECTED_COUNT = 106554

    def test_direct_energy(self):
        q = self.quotes[0]
        self.assertEqual(datetime(2015, 5, 1), q.start_from)
        self.assertEqual(datetime(2015, 6, 1), q.start_until)
        self.assertEqual(6, q.term_months)
        self.assertEqual(datetime(2015, 5, 4), q.valid_from)
        self.assertEqual(datetime(2015, 5, 5), q.valid_until)
        self.assertEqual(0, q.min_volume)
        self.assertEqual(75000, q.limit_volume)
        self.assertEqual(self.ALIASES[0], q.rate_class_alias)
        self.assertEqual(self.RATE_CLASS_ID, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(.07036, q.price)


