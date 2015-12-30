from itertools import chain
from datetime import datetime, timedelta, date
import re
from time import strptime, mktime

from tablib import formats

from brokerage.quote_parser import QuoteParser
from brokerage.reader import parse_number
from brokerage.spreadsheet_reader import SpreadsheetReader
from core.exceptions import ValidationError
from core.model.model import ELECTRIC
from util.dateutils import date_to_datetime, parse_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class GuttmanElectric(QuoteParser):
    """Parser for Guttman Ohio Dominion Gas spreadsheet. This one has energy along the rows and
    time along the columns.
    """
    NAME = 'guttmanelectric'
    reader = SpreadsheetReader(file_format=formats.xlsx)

    EXPECTED_ENERGY_UNIT = unit_registry.kWh

    HEADER_ROW = 7
    RATE_START_ROW = 8
    TERM_MONTHS = [12, 18, 24, 30, 36]
    TITLE_ROW = 3
    TERM_ROW = 7
    TITLE_COL = 'C'
    FIRST_TABLE_TITLE_ROW = 6
    TABLE_ROWS = 13
    START_DATE_COL = 3
    NO_OF_TERM_COLS = 5
    VOLUME_RANGE_COL = 2
    COL_INCREMENT = 8
    PRICE_COL = 4
    ROW_INCREMENT = 16

    def process_table(self, sheet, row, col, rate_class_alias, valid_from, valid_until, min_volume, limit_volume):
        for table_row in xrange(row, row + self.TABLE_ROWS):
            start_from = self._reader.get(sheet, table_row,
                                          self.START_DATE_COL, unicode)
            start_from = parse_datetime(start_from)
            start_until = date_to_datetime((Month(start_from) + 1).first)
            for price_col in xrange(col + 2, col + 2 + self.NO_OF_TERM_COLS):
                term = self._reader.get(sheet, self.TERM_ROW, price_col, int)
                price = self._reader.get(sheet, table_row, price_col, object)
                if isinstance(price, int) and price == 0:
                    continue
                elif price is None:
                    continue
                rate_class_ids = self.get_rate_class_ids_for_alias(
                rate_class_alias)
                for rate_class_id in rate_class_ids:
                    quote = MatrixQuote(
                        start_from=start_from, start_until=start_until,
                        term_months=term, valid_from=valid_from,
                        valid_until=valid_until,
                        min_volume=min_volume,
                        limit_volume=limit_volume,
                        purchase_of_receivables=False, price=price,
                        rate_class_alias=rate_class_alias,
                        service_type=ELECTRIC,
                        file_reference='%s %s,%s' % (
                        self.file_name, sheet, table_row))
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    quote.rate_class_id = rate_class_id
                    yield quote



    def _extract_quotes(self):
        for sheet in [s for s in self.reader.get_sheet_titles() if s != 'Sheet1']:
            valid_from_row = self._reader.get_height(sheet)
            valid_from = self._reader.get(sheet, valid_from_row, 'C', basestring)

            valid_from = datetime.fromtimestamp(mktime(strptime
                                                       (" ".join(re.split(" ", valid_from)[1:]),
                                                        '%m/%d/%Y %I:%M:%S %p')))
            valid_until = valid_from + timedelta(days=1)

            for row in xrange(self.RATE_START_ROW,
                              self._reader.get_height(sheet),
                              self.ROW_INCREMENT):
                self.TERM_ROW = self.TERM_ROW + ((row - 1) - self.TERM_ROW)
                for col in xrange(self.VOLUME_RANGE_COL,
                                  self._reader.get_width(sheet),
                                  self.COL_INCREMENT):
                    volume_column = self._reader.get(sheet, row, col, object)
                    if volume_column is not None and 'kWh' in volume_column:
                        min_volume, limit_volume = self._extract_volume_range(
                            sheet, row, col,
                            r'.*[_ ](?P<low>[\d,]+)'
                            r'(?: - |-)(?P<high>[\d,]+)'
                            r'(?:-kWh)',
                            expected_unit=unit_registry.kwh,
                            target_unit=unit_registry.kwh)
                    else:
                        continue

                    rate_class_alias = self._reader.get(sheet,
                                                        self.TITLE_ROW,
                                                        self.TITLE_COL,
                                                        basestring)
                    regex = r'([A-Z0-9]+(?:_[A-Z]+|-[0-9]+|[0-9]+|[A-Z]+|' \
                            r'[0-9]+|_[A-Z]+\>[0-9]+|_[A-Z]+\<[0-9]+))'
                    rate_class = self._reader.get_matches(sheet, row, col,
                                                          regex, str)
                    rate_class_alias = rate_class_alias + '_' + \
                                       rate_class
                    quotes = self.process_table(sheet, row, col,
                                                rate_class_alias, valid_from,
                                                valid_until, min_volume,
                                                limit_volume)
                    for quote in quotes:
                        yield quote




