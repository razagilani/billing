""" Spreadsheet parser for Great Eastern Energy (GEE).

It is important to note that GEE contains separate spreadsheets for each
state in which it does business. Fortunately, they are all of the same
format, so only one parser needs to be used.
"""

from tablib import formats

from util.units import unit_registry
from brokerage.quote_parser import QuoteParser, SimpleCellDateGetter, \
    SpreadsheetReader

class GEEPriceQuote(object):
    """ Represents a price cell in the spreadsheet and contains
        the rules to find or calculate each of its properties """

    def __init__(self, matrix_parser, reader, sheet, row, col):
        self.matrix_parser = matrix_parser
        self.reader = reader
        self.sheet = sheet
        self.row = row
        self.col = col

    def evaluate(self):
        raise NotImplemented

    def fetch_term(self):
        pass

    def fetch_rate_sch(self):
        pass

    def fetch_zone(self):
        pass

class GEEMatrixParser(QuoteParser):
    """Parser class for Great Electric Energy (GEE) spreadsheets."""

    # Question: Is this correct?
    NAME = 'greatelectricenergy'

    READER_CLASS = SpreadsheetReader
    FILE_FORMAT = formats.xlsx
    EXPECTED_ENERGY_UNIT = unit_registry.kWh

    ZONE_COL = 0
    RATE_SCH_COL = 1
    TERM_COL = 2
    START_DATE_LBL_COL = 3




