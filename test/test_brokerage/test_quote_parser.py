from datetime import datetime
from os import path
from unittest import TestCase
from core import ROOT_PATH
from brokerage.read_quotes import DirectEnergyMatrixParser

class DirectEnergyParserTest(TestCase):
    EXAMPLE_FILE_PATH = path.join(ROOT_PATH, 'test', 'test_brokerage',
                                  'Matrix 1 Example - Direct Energy.xls')

    def setUp(self):
        self.parser = DirectEnergyMatrixParser()

    def test_read_file(self):
        """Load a real file and get quotes out of it.
        """
        with open(self.EXAMPLE_FILE_PATH, 'rb') as spreadsheet:
            self.parser.load_file(spreadsheet)
        self.parser.validate()

        quotes = list(self.parser.extract_quotes())
        self.assertEqual(61554, len(quotes))
        for quote in quotes:
            quote.validate()

        # since there are so many, only check one
        q1 = quotes[0]
        self.assertEqual(datetime(2014, 12, 1), q1.start_from)
        self.assertEqual(datetime(2015, 1, 1), q1.start_until)
        self.assertEqual(12, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2014, 12, 1), q1.valid_from)
        self.assertEqual(datetime(2014, 12, 2), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(75.0, q1.limit_volume)
