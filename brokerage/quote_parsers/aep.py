import datetime
import time
from decimal import Decimal
from tablib import formats

from brokerage.quote_parser import QuoteParser, \
    excel_number_to_datetime, SimpleCellDateGetter
from brokerage.spreadsheet_reader import SpreadsheetReader
from brokerage.validation import _assert_true
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class AEPMatrixParser(QuoteParser):
    """Parser for AEP Energy spreadsheet.
    """
    NAME = 'aep'
    reader = SpreadsheetReader(formats.xls)

    EXPECTED_SHEET_TITLES = [
        'Price Finder', 'Customer Information', 'Matrix Table-FPAI',
        'Matrix Table-Energy Only', 'PLC Load Factor Calculator']

    # FPAI is "Fixed-Price All-In"; we're ignoring the "Energy Only" quotes
    SHEET = 'Matrix Table-FPAI'

    EXPECTED_CELLS = [
        (SHEET, 3, 'E', 'Matrix Pricing'),
        (SHEET, 3, 'V', 'Date of Matrix:'),
        (SHEET, 4, 'V', 'Pricing Valid Thru:'),
        (SHEET, 7, 'C', r'Product: Fixed Price All-In \(FPAI\)'),
        (SHEET, 8, 'C', 'Aggregate Size Max: 1,000 MWh/Yr'),
        (SHEET, 9, 'C', r'Pricing Units: \$/kWh'),
        (SHEET, 7, 'I',
         r"1\) By utilizing AEP Energy's Matrix Pricing, you agree to follow "
         "the  Matrix Pricing Information, Process, and Guidelines document"),
        (SHEET, 8, 'I',
         r"2\) Ensure sufficient time to enroll for selected start month; "
         "enrollment times vary by LDC"),
        (SHEET, 11, 'I', "Customer Size: 0-100 Annuals MWhs"),
        (SHEET, 11, 'M', "Customer Size: 101-250 Annuals MWhs"),
        (SHEET, 11, 'Q', "Customer Size: 251-500 Annuals MWhs"),
        (SHEET, 11, 'U', "Customer Size: 501-1000 Annuals MWhs"),
        (SHEET, 13, 'C', "State"),
        (SHEET, 13, 'D', "Utility"),
        (SHEET, 13, 'E', r"Profile"),
        (SHEET, 13, 'F', "Rate Code\(s\)/Description"),
        (SHEET, 13, 'G', "Start Month"),
    ]

    VOLUME_RANGE_ROW = 11
    HEADER_ROW = 13
    QUOTE_START_ROW = 14
    STATE_COL = 'C'
    UTILITY_COL = 'D'
    RATE_CODES_COL = 'E'
    # TODO what is "rate code(s)" in col E?
    RATE_CLASS_COL = 'F'
    START_MONTH_COL = 'G'

    EXPECTED_ENERGY_UNIT = unit_registry.MWh
    TARGET_ENERGY_UNIT = unit_registry.kWh

    # columns for headers like "Customer Size: 101-250 Annuals MWhs"
    VOLUME_RANGE_COLS = ['I', 'M', 'Q', 'U']

    # TODO: prices are valid until 6 PM CST = 7 PM EST according to cell
    # below the date cell
    date_getter = SimpleCellDateGetter(SHEET, 3, 'W', None)

    def _extract_quotes(self):
        for row in xrange(self.QUOTE_START_ROW,
                          self.reader.get_height(self.SHEET)):
            state = self.reader.get(self.SHEET, row, self.STATE_COL,
                                    basestring)
            # blank line means end of sheet
            if state == '':
                continue

            utility = self.reader.get(self.SHEET, row, self.UTILITY_COL,
                                      basestring)
            state = self.reader.get(self.SHEET, row,
                                    self.STATE_COL, basestring)
            rate_codes = self.reader.get(self.SHEET, row,
                                         self.RATE_CODES_COL, basestring)
            rate_class = self.reader.get(self.SHEET, row,
                                         self.RATE_CLASS_COL, basestring)
            rate_class_alias = '-'.join([state, utility, rate_codes,rate_class])

            # TODO use time zone here
            start_from = excel_number_to_datetime(
                self.reader.get(self.SHEET, row, self.START_MONTH_COL,
                                float))
            start_until = date_to_datetime((Month(start_from) + 1).first)

            for i, vol_col in enumerate(self.VOLUME_RANGE_COLS):
                min_volume, limit_volume = self._extract_volume_range(
                    self.SHEET, self.VOLUME_RANGE_ROW, vol_col,
                    r'Customer Size: (?P<low>\d+)-(?P<high>\d+) Annuals MWhs',
                    fudge_low=True)

                # TODO: ugly
                try:
                    next_vol_col = self.VOLUME_RANGE_COLS[i + 1]
                except IndexError:
                    next_vol_col = 'X'

                for col in self.reader.column_range(vol_col, next_vol_col,
                                                    inclusive=False):
                    # skip column that says "End May '18" since we don't know
                    # what contract length that really is
                    if self.reader.get(
                            self.SHEET, self.HEADER_ROW, col,
                            (basestring, float, int)) == "End May '18":
                        continue
                    # TODO: extracted unnecessarily many times
                    term = int(self.reader.get(
                        self.SHEET, self.HEADER_ROW, col, (int, float)))

                    price = self.reader.get(self.SHEET, row, col,
                                            (float, basestring, type(None)))
                    # skip blanks
                    if price in (None, ""):
                        continue
                    _assert_true(type(price) is float)

                    for rate_class_id in self.get_rate_class_ids_for_alias(
                            rate_class_alias):
                        quote = MatrixQuote(
                            start_from=start_from, start_until=start_until,
                            term_months=term, valid_from=self._valid_from,
                            valid_until=self._valid_until,
                            min_volume=min_volume, limit_volume=limit_volume,
                            purchase_of_receivables=False,
                            rate_class_alias=rate_class_alias, price=price,
                            service_type='electric',
                            file_reference='%s %s,%s,%s' % (
                                self.file_name, self.SHEET, row, col))
                        quote.rate_class_id = rate_class_id
                        yield quote
