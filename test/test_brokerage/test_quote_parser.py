from datetime import datetime
from os import path
from unittest import TestCase
from core import ROOT_PATH
from brokerage.quote_parsers import DirectEnergyMatrixParser

class DirectEnergyParserTest(TestCase):
    EXAMPLE_FILE_PATH = path.join(ROOT_PATH, 'test', 'test_brokerage',
                                  'Matrix 1 Example - Direct Energy.xls')

    def setUp(self):
        self.parser = DirectEnergyMatrixParser()

    def test_read_file(self):
        """Load a real file and get quotes out of it.
        """
        self.assertEqual(0, self.parser.get_count())

        with open(self.EXAMPLE_FILE_PATH, 'rb') as spreadsheet:
            self.parser.load_file(spreadsheet)
        self.parser.validate()
        self.assertEqual(0, self.parser.get_count())

        quotes = list(self.parser.extract_quotes())
        self.assertEqual(204474, len(quotes))
        self.assertEqual(204474, self.parser.get_count())
        for quote in quotes:
            quote.validate()

        # since there are so many, only check one
        q1 = quotes[0]
        self.assertEqual(datetime(2015, 5, 1), q1.start_from)
        self.assertEqual(datetime(2015, 6, 1), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2015, 5, 4), q1.valid_from)
        self.assertEqual(datetime(2015, 5, 5), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual('37', q1.rate_class_alias)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(.7036, q1.price)
