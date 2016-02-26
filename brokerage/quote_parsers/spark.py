from datetime import datetime

from tablib import formats

from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import QuoteParser, SpreadsheetReader, \
    SimpleCellDateGetter
from util.dateutils import date_to_datetime
from util.monthmath import Month
from util.units import unit_registry


class SparkMatrixParser(QuoteParser):
    NAME = 'spark'
    reader = SpreadsheetReader(formats.xlsx)

    HEADER_ROW = 7
    RCA_COLS = ['A', 'B', 'C', 'E']
    START_COL = 'F'
    VOLUME_RANGE_COL = 'H'
    PRICE_COLS = reader.column_range('I', 'M')

    EXPECTED_SHEET_TITLES = [ 'LED Matrix' ]
    SHEET = 'LED Matrix'

    EXPECTED_CELLS = [
        (SHEET, 2, 'A', 'Effective Date'),
        (SHEET, HEADER_ROW, 'A', 'STATE'),
        (SHEET, HEADER_ROW, 'B', 'UTILITY'),
        (SHEET, HEADER_ROW, 'C', 'LOAD ZONE'),
        (SHEET, HEADER_ROW, 'E', 'PROFILES'),
        (SHEET, HEADER_ROW, START_COL, 'START DATE'),
        (SHEET, HEADER_ROW, VOLUME_RANGE_COL, 'ANNUAL USAGE.*'),
    ]

    date_getter = SimpleCellDateGetter(SHEET, 3, 'A', None)

    ROUNDING_DIGITS = 4

    def _extract_quotes(self):
        for row in xrange(self.HEADER_ROW + 1,
                          self.reader.get_height(self.SHEET) + 1):
            rate_class_alias = '-'.join(self.reader.get(
                self.SHEET, row, col, basestring) for col in self.RCA_COLS)
            start_from = self.reader.get(
                self.SHEET, row, self.START_COL, datetime)
            start_until = date_to_datetime((Month(start_from) + 1).first)

            min_vol, limit_vol = self._extract_volume_range(
                self.SHEET, row, self.VOLUME_RANGE_COL,
                '(?P<low>[\d,]+) to (?P<high>[\d,]+)', fudge_low=True,
                expected_unit=unit_registry.kWh)

            for col in self.PRICE_COLS:
                term = self.reader.get_matches(
                    self.SHEET, self.HEADER_ROW, col, '(\d+) MTHS', int)
                price = self.reader.get(self.SHEET, row, col, float)

                for rate_class_id in self.get_rate_class_ids_for_alias(
                        rate_class_alias):
                    quote = MatrixQuote(
                        start_from=start_from, start_until=start_until,
                        term_months=term, valid_from=self._valid_from,
                        valid_until=self._valid_until,
                        min_volume=min_vol, limit_volume=limit_vol,
                        rate_class_alias=rate_class_alias,
                        price=price, service_type='electric',
                        file_reference='%s %s,%s,%s' % (
                            self.file_name, self.SHEET, row, col))
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote
