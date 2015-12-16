from itertools import chain
from datetime import datetime, timedelta, date
import re
from time import strptime, mktime

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
    TITLE_ROW = 3
    TITLE_COL = 'c'
    START_DATE_COL = 'D'
    TERM_COL = 'E'
    VOLUME_RANGE_COL = 'F'
    PRICE_COL = 'G'


    EXPECTED_SHEET_TITLES = [
        'Detail',
        'Summary'
    ]

    EXPECTED_CELLS = list(chain.from_iterable([
            (sheet, 6, 2, 'Count'),
            (sheet, 6, 3, 'Start'),
            (sheet, 6, 4, 'Term'),
            (sheet, 6, 5, 'Annual kWh'),
            (sheet, 6, 6, 'Price ($/Dth)')
        ] for sheet in [s for s in EXPECTED_SHEET_TITLES if s != 'Summary']))

    def _extract_volume_range(self, sheet, row, col):
        regex = r'(EAST|WEST)_([\d,]+)-([\d,]+)_MCF'
        direction, low, high = self._reader.get_matches(sheet, row, col, regex,
                                                 (unicode, parse_number,
                                                 parse_number))
        return direction, low, high

    def _extract_quotes(self):
        title = self._reader.get(0, self.TITLE_ROW, self.TITLE_COL,
                                 basestring)
        title_tokens = re.split("_", title)
        state = title_tokens[0]
        utility = title_tokens[1]
        unit = title_tokens[4]
        valid_from_row = self._reader.get_height(0)
        valid_from = self._reader.get(0, valid_from_row, 'C', basestring)

        valid_from = datetime.fromtimestamp(mktime(strptime
                            (" ".join(re.split(" ", valid_from)[1:]),
                              '%m/%d/%Y %I:%M:%S %p')))
        valid_until = valid_from + timedelta(days=1)
        rate_class_alias = self._reader.get(0, 3, 'C', basestring)
        for sheet in [s for s in self.EXPECTED_SHEET_TITLES if
                    s != 'Summary']:
            for row in xrange(self.RATE_START_ROW,
                              self._reader.get_height(sheet) + 1):
                term = self._reader.get(sheet, row, self.TERM_COL, int)
                direction, min_volume, limit_volume = \
                    self._extract_volume_range(sheet, row,
                                               self.VOLUME_RANGE_COL)
                start_from = self._reader.get(sheet, row,
                                              self.START_DATE_COL, unicode)
                start_from = datetime.fromtimestamp(mktime(strptime(
                    start_from+str(date.today().year),'%b-%d%Y')))
                if start_from is None:
                    continue
                start_until = date_to_datetime((Month(start_from) + 1).first)
                price = self._reader.get(sheet, row, self.PRICE_COL, object)
                if isinstance(price, int) and price == 0:
                    continue
                elif price is None:
                    continue
                elif isinstance(price, float):
                    # the unit is $/mcf
                    price /= 1000.
                rate_class_alias = '-'.join(['Guttman', 'gas', state,
                    utility, direction, str(min_volume), str(limit_volume)])
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
                        service_type='gas')
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    quote.rate_class_id = rate_class_id
                    yield quote




