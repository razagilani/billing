""" Spreadsheet parser for Great Eastern Energy (GEE).

It is important to note that GEE contains separate spreadsheets for each
state in which it does business. Fortunately, they are all of the same
format, so only one parser needs to be used.
"""

import datetime
import re

from tablib import formats

from util.units import unit_registry
from brokerage.quote_parser import QuoteParser, SimpleCellDateGetter, \
    SpreadsheetReader
from brokerage.brokerage_model import MatrixQuote

class GEEPriceQuote(object):
    """ Represents a price cell in the spreadsheet and contains
        the rules to find or calculate each of its properties """

    MAX_SEARCH_CNT = 10

    def __init__(self, matrix_parser, reader, sheet, row, col):
        self.matrix_parser = matrix_parser
        self.reader = reader
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
            rate_class_alias=self.self.fetch_alias()
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
                start_str = self._reader.get_matches(
                    self.sheet, self.row - row_offset, self.col, r'([a-zA-Z]{3}-[\d]{2})', basestring)
                start_from = datetime.datetime.strptime(start_str, '%b-%y')
                start_until = start_from + datetime.timedelta(months=1)

                return (start_from, start_until)
            except:
                # TODO - This exception needs to be specified - I don't know what it is though.
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
    FIRST_QUOTE_COL = 'D'




