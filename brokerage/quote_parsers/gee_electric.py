""" Spreadsheet parser for Great Eastern Energy (GEE).

It is important to note that GEE contains separate spreadsheets for each
state in which it does business. Fortunately, they are all of the same
format, so only one parser needs to be used.
"""

import datetime
import re

from tablib import formats

from dateutil.relativedelta import relativedelta

from core.exceptions import ValidationError
from util.units import unit_registry
from brokerage.quote_parser import QuoteParser, SimpleCellDateGetter, \
    SpreadsheetReader
from brokerage.brokerage_model import MatrixQuote


class GEEPriceQuote(object):
    """ Represents a price cell in the spreadsheet and contains
        the rules to find or calculate each of its properties """

    MAX_SEARCH_CNT = 10

    def __init__(self, matrix_parser, sheet, row, col):
        self.matrix_parser = matrix_parser
        self.reader = matrix_parser._reader
        self.sheet = sheet
        self.row = row
        self.col = col

    def evaluate(self):
        start_from, start_until = self.fetch_start_dates()
        min_volume, limit_volume = self.fetch_volume_range()

        return MatrixQuote(
            price=self.fetch_price(),
            start_from=start_from,
            start_until=start_until,
            term_months=self.fetch_term(),
            valid_from=self.matrix_parser._valid_from,
            valid_until=self.matrix_parser._valid_until,
            min_volume=min_volume,
            limit_volume=limit_volume,
            purchase_of_receivables=False,
            rate_class_alias=self.fetch_alias()
        )

    def fetch_price(self):
        return self.reader.get(self.sheet, self.row, self.col, float)

    def fetch_alias(self):
        # This format is taken per a discussion with Chris Wagner
        # captured in JIRA BILL-6632.

        # First token of spreadsheet (this is utility name)
        utility = self.sheet.split(' ')[0]
        return "GEE-electric-{0}-{1}-{2}".format(
            utility,
            self.fetch_zone(),
            self.fetch_rate_sch()
        )

    def fetch_term(self):
        return self.reader.get(self.sheet, self.row, self.matrix_parser.TERM_COL, int)

    def fetch_rate_sch(self):
        return self.reader.get(self.sheet, self.row, self.matrix_parser.RATE_SCH_COL, basestring)

    def fetch_zone(self):
        # Special notes:
        # * If Zone contains "Sweet Spot", remove that label and add it as usual
        # * If Zone contains "Custom" - ignore everythign in that row.
        # BUT - This probably should not be done here.
        return self.reader.get(self.sheet, self.row, self.matrix_parser.ZONE_COL, basestring)

    def fetch_start_dates(self):
        # Search for the start date row
        for row_offset in xrange(0, self.MAX_SEARCH_CNT):
            try:
                start_date = self.reader.get(
                    self.sheet,
                    max(0, self.row - row_offset),
                    self.col,
                    datetime.datetime)
                start_from = datetime.datetime(start_date.year, start_date.month, 1)
                start_until = start_from + relativedelta(months=1)
                return (start_from, start_until)
            except ValidationError as e:
                pass
        else:
            # After going through MAX_SEARCH_CNT cells - could not find a date.
            raise ValueError('Cannot find start date for quote')

    def fetch_volume_range(self):
        # This is mostly located in the sheet title.
        vol_ranges = re.search(r'([\d]+)K?-([\d]+)K', self.sheet)
        min_vol_kwh = int(vol_ranges.groups()[0]) * 1000
        limit_vol_kwh = ((int(vol_ranges.groups()[1]) + 1) * 1000) - 1
        return min_vol_kwh, limit_vol_kwh


class GEEMatrixParser(QuoteParser):
    """Parser class for Great Electric Energy (GEE) spreadsheets."""

    # Question: Is this correct?
    NAME = 'greatelectricenergy'

    READER_CLASS = SpreadsheetReader
    FILE_FORMAT = formats.xlsx
    EXPECTED_ENERGY_UNIT = unit_registry.kWh

    ZONE_COL = 'A'
    RATE_SCH_COL = 'B'
    TERM_COL = 'C'
    START_DATE_LBL_COL = 'D'
    FIRST_QUOTE_COL = 3
    EFFECTIVE_DATE_COL = 'F'
    EFFECTIVE_DATE_ROW = 2

    ASSUMED_PRICE_ROW_START = 6

    def _validate(self):
        pass

    def _extract_quotes(self):

        # First, we need to get the validitity dates for all quotes. This is a little annoying
        # because it is ONLY available on the first sheet of each spreadsheet.
        effective_str = self._reader.get(0, self.EFFECTIVE_DATE_ROW, self.EFFECTIVE_DATE_COL, basestring)
        effective_date = datetime.datetime.strptime(effective_str.split(':')[1].strip(), '%B %d, %Y')
        self._valid_from = effective_date
        self._valid_util = effective_date + datetime.timedelta(days=1)

        for sheet in self._reader.get_sheet_titles():
            if not re.search(r'([\d]+K?-[\d]{3})', sheet):
                # For now - only parse sheets that have volume ranges
                continue

            start_row = self.ASSUMED_PRICE_ROW_START
            for test_row in xrange(0, self._reader.get_height(sheet)):
                cell_val= self._reader.get(sheet, test_row, self.ZONE_COL, (basestring, type(None)))
                if cell_val == 'Zone':
                    start_row = test_row + 2
                    break

            for price_row in xrange(start_row, self._reader.get_height(sheet)):
                for price_col in xrange(self.FIRST_QUOTE_COL, self._reader.get_width(sheet)):
                    try:
                        print sheet, price_row, price_col
                        price = self._reader.get(sheet, price_row, price_col, float)
                    except ValidationError:
                        continue

                    try:
                        x = self
                        quote = GEEPriceQuote(x, sheet, price_row, price_col).evaluate()
                        if 'custom' not in quote.rate_class_alias.lower():
                            yield quote
                    except Exception as e:
                        raise
