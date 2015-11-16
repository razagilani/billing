from unittest import TestCase
from brokerage.quote_parser import SpreadsheetReader

class SpreadsheetReaderTest(TestCase):
    """Unit tests for SpreadsheetReader.
    """

    def setUp(self):
        pass

    def test_col_letter_to_index(self):
        with self.assertRaises(ValueError):
            SpreadsheetReader.col_letter_to_index('[')
        self.assertEqual(0, SpreadsheetReader.col_letter_to_index('A'))
        self.assertEqual(0, SpreadsheetReader.col_letter_to_index('a'))
        self.assertEqual(1, SpreadsheetReader.col_letter_to_index('B'))
        self.assertEqual(25, SpreadsheetReader.col_letter_to_index('Z'))
        self.assertEqual(26, SpreadsheetReader.col_letter_to_index('AA'))
        self.assertEqual(26, SpreadsheetReader.col_letter_to_index('aA'))
        self.assertEqual(51, SpreadsheetReader.col_letter_to_index('AZ'))
        self.assertEqual(52, SpreadsheetReader.col_letter_to_index('BA'))

    def test_column_range(self):
        # empty ranges
        self.assertEqual([], SpreadsheetReader.column_range(1, 0))
        self.assertEqual([],
                         SpreadsheetReader.column_range(0, 0, inclusive=False))
        self.assertEqual([], SpreadsheetReader.column_range(10, 5, step=3))

        # 1-length ranges
        self.assertEqual([0], SpreadsheetReader.column_range(0, 0))
        self.assertEqual([0],
                         SpreadsheetReader.column_range(0, 1, inclusive=False))
        self.assertEqual([100], SpreadsheetReader.column_range(100, 100))
        self.assertEqual([0], SpreadsheetReader.column_range('A', 'a'))
        self.assertEqual([52], SpreadsheetReader.column_range('BA', 'BA'))

        # nonempty ranges with default step (1)
        self.assertEqual([0, 1], SpreadsheetReader.column_range(0, 1))
        self.assertEqual([3, 4, 5], SpreadsheetReader.column_range('D', 'F'))
        self.assertEqual(
            [3, 4], SpreadsheetReader.column_range('D', 'F', inclusive=False))
        self.assertEqual(range(49, 54),
                         SpreadsheetReader.column_range('AX', 'BB'))

        # ranges with step
        self.assertEqual([0], SpreadsheetReader.column_range(0, 1, step=2))
        self.assertEqual([0, 3, 6],
                         SpreadsheetReader.column_range('A', 'G', step=3))

        # backwards range is not supported
        self.assertEqual([], SpreadsheetReader.column_range(1, 0, step=-1))
