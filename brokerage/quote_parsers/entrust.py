from itertools import chain
from datetime import datetime
from tablib import formats

from brokerage.quote_parser import _assert_true, QuoteParser, \
    excel_number_to_datetime, StartEndCellDateGetter, SimpleCellDateGetter, \
    _assert_equal, SpreadsheetReader
from exc import ValidationError
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class EntrustMatrixParser(QuoteParser):
    """Parser for Entrust spreadsheet.
    """
    FILE_FORMAT = formats.xlsx

    EXPECTED_SHEET_TITLES = [
        'IL - ComEd Matrix',
        'OH - Duke Matrix',
        'OH - Dayton Matrix',
        'PA - PECO Matrix',
        'PA - PPL Matrix',
        'MD - BGE Matrix',
        'MD - PEPCO Matrix',
        'NJ - JCPL Matrix',
        'NYSEG - A - Matrix',
        'NYSEG - B - Matrix',
        'NYSEG - C - Matrix',
        'NYSEG - D - Matrix',
        'NYSEG - E - Matrix',
        'NYSEG - F - Matrix',
        'NYSEG - G - Matrix',
        'NYSEG - H - Matrix',
        'NYSEG - I - Matrix',
        'NY - NATGRID - A - Matrix',
        'NY - NATGRID - B - Matrix',
        'NY - NATGRID - C - Matrix',
        'NY - NATGRID - D - Matrix',
        'NY - NATGRID - E - Matrix',
        'RG&E - B - Matrix',
        'ConEd - H - Matrix',
        'ConEd - I - Matrix',
        'ConEd - J - Matrix']

    DATE_REGEX = ('Pricing for Commercial Customers\s+'
                 'for (\w+ \w+ \d\d?, \d\d\d\d)')
    EXPECTED_CELLS = chain.from_iterable(
        [[(sheet, 4, 'F', DATE_REGEX),
          (sheet, 6, 'D', 'Utility'),
          (sheet, 7, 'D', 'Annual Usage'),
          (sheet, 8, 'D', 'Term \(months\)'),
          (sheet, 9, 'C', 'Start Month'),
          ] for sheet in EXPECTED_SHEET_TITLES])

    DATE_ROW = 5
    UTILITY_ROW = 6
    VOLUME_RANGE_ROW = 7
    QUOTE_START_ROW = 9
    START_COL = 'D'
    UTILITY_COL = 'E'
    PRICE_START_COL = 'E'
    DATE_COL = 'F'
    VOLUME_RANGE_COLS = ['E', 'L', 'S', 'Z']

    EXPECTED_ENERGY_UNIT = unit_registry.kWh

    date_getter = SimpleCellDateGetter(0, 4, 'F', DATE_REGEX)

    def _validate(self):
        all_dates = [
            self._reader.get(sheet, self.DATE_ROW, self.DATE_COL, object) for
            sheet in self.EXPECTED_SHEET_TITLES]
        if not all(all_dates[0] == d for d in all_dates):
            raise ValidationError('Dates are not the same in all sheets')

    def _process_sheet(self, sheet):
        # could get the utility from the sheet name, but this seems better
        utility = self._reader.get(sheet, self.UTILITY_ROW, self.UTILITY_COL,
                                   basestring)
        max_only_regex = r'<\s*(?P<high>[\d,]+)\s*kWh Annually'
        min_and_max_regex = r'\s*(?P<low>[\d,]+)\s*<\s*kWh Annually\s*<\s*(?P<high>[\d,]+)'
        volume_ranges = [
            self._extract_volume_range(sheet, self.VOLUME_RANGE_ROW,
                                       self.VOLUME_RANGE_COLS[0],
                                       max_only_regex)] + [
            self._extract_volume_range(sheet, self.VOLUME_RANGE_ROW, col,
                                       min_and_max_regex) for col in
            self.VOLUME_RANGE_COLS[1:]]
        print volume_ranges

        for row in xrange(self.QUOTE_START_ROW,
                          self._reader.get_height(sheet)):
            start_from = self._reader.get(sheet, row, self.START_COL, datetime)

            for col in SpreadsheetReader.column_range(
                    self.PRICE_START_COL, self._reader.get_width(sheet),
                    inclusive=False):
                price = self._reader.get(sheet, row, col, object)
                print price

    def _extract_quotes(self):
        for sheet in self.EXPECTED_SHEET_TITLES:
            self._process_sheet(sheet)
