from itertools import chain
from datetime import datetime

from tablib import formats

from brokerage.quote_parser import QuoteParser, SimpleCellDateGetter, \
    SpreadsheetReader
from core.exceptions import ValidationError
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class EntrustMatrixParser(QuoteParser):
    """Parser for Entrust spreadsheet.
    """
    NAME = 'entrust'
    reader = SpreadsheetReader(formats.xlsx)

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

    DATE_ROW = 4
    UTILITY_ROW = 6
    VOLUME_RANGE_ROW = 7
    TERM_ROW = 8
    QUOTE_START_ROW = 9
    START_COL = 'D'
    UTILITY_COL = 'E'
    PRICE_START_COL = 'E'
    DATE_COL = 'F'
    # certain columns have term length in a different place
    # (indices are used instead of letters to enable comparison)
    # each of the prices has a corresponding term in the cell whose row is
    # the same and whose column is at the same index in the second list
    SWEET_SPOT_PRICE_COLS = [8, 15, 22, 29]
    SWEET_SPOT_TERM_COLS = [x + 1 for x in SWEET_SPOT_PRICE_COLS]

    VOLUME_RANGE_COLS = ['E', 'L', 'S', 'Z']

    EXPECTED_ENERGY_UNIT = unit_registry.kWh

    date_getter = SimpleCellDateGetter(0, DATE_ROW, 'F', DATE_REGEX)

    def _validate(self):
        # since only the first sheet is the offical source of the date,
        # make sure all others have the same date in them
        all_dates = [
            self.reader.get(sheet, self.DATE_ROW, self.DATE_COL, object) for
            sheet in self.EXPECTED_SHEET_TITLES]
        if not all(all_dates[0] == d for d in all_dates):
            raise ValidationError('Dates are not the same in all sheets')

    def _process_sheet(self, sheet):
        # could get the utility from the sheet name, but this seems better.
        # includes utility and zone name.
        utility = self.reader.get(sheet, self.UTILITY_ROW, self.UTILITY_COL,
                                  basestring)
        rate_class_alias = utility
        rate_class_ids = self.get_rate_class_ids_for_alias(rate_class_alias)

        # they spell "Annually" wrong in some columns
        max_only_regex = r'<\s*(?P<high>[\d,]+)\s*kWh Annuall?y'
        min_and_max_regex = (r'\s*(?P<low>[\d,]+)\s*<\s*kWh Annuall?y\s*<'
                             r'\s*(?P<high>[\d,]+)\s*')
        volume_ranges = [
            self._extract_volume_range(sheet, self.VOLUME_RANGE_ROW,
                                       self.VOLUME_RANGE_COLS[0],
                                       max_only_regex)] + [
            self._extract_volume_range(sheet, self.VOLUME_RANGE_ROW, col,
                                       min_and_max_regex) for col in
            self.VOLUME_RANGE_COLS[1:]]
        # width of volume range block includes 4 regular columns,
        # 2 "Sweet Spot" columns, and 1 empty space
        first_vol_range_index = SpreadsheetReader.col_letter_to_index(
            self.VOLUME_RANGE_COLS[0])
        vol_range_block_width = len(self.VOLUME_RANGE_COLS) + 3

        for row in xrange(self.QUOTE_START_ROW,
                          self.reader.get_height(sheet) + 1):
            start_from = self.reader.get(sheet, row, self.START_COL, datetime)
            start_until = date_to_datetime((Month(start_from) + 1).first)

            for col in SpreadsheetReader.column_range(
                    self.PRICE_START_COL, self.reader.get_width(sheet),
                    inclusive=False):
                if col in self.SWEET_SPOT_TERM_COLS:
                    # not a price, but the term length for the previous column
                    continue
                price = self.reader.get(sheet, row, col, object)
                if price is None:
                    # blank space
                    continue

                if col in self.SWEET_SPOT_PRICE_COLS:
                    # this price has its term length in the next column, which
                    # is in the corresponding position in SWEET_SPOT_TERM_COLS
                    term_col = self.SWEET_SPOT_TERM_COLS[
                        self.SWEET_SPOT_PRICE_COLS.index(col)]
                    term_months = self.reader.get_matches(
                        sheet, row, term_col, '(\d+) Months', int)
                else:
                    min_volume, limit_volume = volume_ranges[
                        (col - first_vol_range_index) / vol_range_block_width]
                    term_months = self.reader.get(
                        sheet, self.TERM_ROW, col, int)

                for rate_class_id in rate_class_ids:
                    quote = MatrixQuote(
                        start_from=start_from, start_until=start_until,
                        term_months=term_months, valid_from=self._valid_from,
                        valid_until=self._valid_until,
                        min_volume=min_volume, limit_volume=limit_volume,
                        rate_class_alias=rate_class_alias,
                        purchase_of_receivables=False, price=price,
                        service_type='electric',
                        file_reference='%s %s,%s,%s' % (
                            self.file_name, self.sheet, row, col))
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote

    def _extract_quotes(self):
        for sheet in self.EXPECTED_SHEET_TITLES:
            for quote in self._process_sheet(sheet):
                yield quote
