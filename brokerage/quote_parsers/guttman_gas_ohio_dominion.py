from itertools import chain
from datetime import datetime, timedelta

from tablib import formats

from brokerage.quote_parser import QuoteParser
from brokerage.reader import parse_number
from brokerage.spreadsheet_reader import SpreadsheetReader
from core.exceptions import ValidationError
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote

class GuttmanGasOhioDominion(QuoteParser):
    """Parser for Guttman Ohio Dominion Gas spreadsheet. This one has energy along the rows and
    time along the columns.
    """
    NAME = 'guttmangasohiodominion'
    READER_CLASS = SpreadsheetReader
    FILE_FORMAT = formats.xlsx

    HEADER_ROW = 6
    RATE_START_ROW = 7

    EXPECTED_SHEET_TITLES = [
        'Detail',
        'Summary'
    ]

    EXPECTED_CELLS = list(chain.from_iterable([
            (sheet, 6, 2, 'Count'),
            (sheet, 6, 3, 'Start'),
            (sheet, 6, 4, 'Term'),
            (sheet, 6, 5, 'Annual kWh'),
            (sheet, 6, 6, 'Price ($/Dth)'),
            (sheet, 5, 3, 'Annual Usage Tier')
        ] for sheet in [s for s in EXPECTED_SHEET_TITLES if s != 'Summary']))

    def _extract_volume_range(self, sheet, row, col):
        regex = r'(EAST|WEST)_([\d,]+)-([\d,]+)_MCF'
        _, low, high = self._reader.get_matches(sheet, row, col, regex,
                                                 (basestring, parse_number,
                                                 parse_number))
        return low, high

    def _extract_quotes(self):
        valid_from_row = self._reader.get_height(0)
        valid_from = self._reader.get(0, valid_from_row, 'C', datetime)
        valid_until = valid_from + timedelta(days=1)
        rate_class_alias = self._reader.get(0, 3, 'C', basestring)
        for sheet in [s for s in self.EXPECTED_SHEET_TITLES if s != 'Summary']:
            for row in xrange(self.RATE_START_ROW,
                              self._reader.get_height(sheet) + 1):



