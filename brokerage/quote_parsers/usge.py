from itertools import chain
from datetime import datetime

from tablib import formats

from brokerage.quote_parser import QuoteParser, SimpleCellDateGetter
from brokerage.reader import parse_number
from brokerage.spreadsheet_reader import SpreadsheetReader
from core.exceptions import ValidationError
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote


class USGEMatrixParser(QuoteParser):
    """Parser for USGE spreadsheet. This one has energy along the rows and
    time along the columns.
    """
    NAME = 'usgegas'
    reader = SpreadsheetReader(formats.xlsx)

    FILE_FORMAT = formats.xlsx

    TERM_HEADER_ROW = 4
    HEADER_ROW = 5
    RATE_START_ROW = 6
    RATE_END_ROW = 34
    UTILITY_COL = 0
    VOLUME_RANGE_COL = 3
    RATE_END_COL = 11
    TERM_START_COL = 6
    TERM_END_COL = 28
    LDC_COL = 'A'
    CUSTOMER_TYPE_COL = 'B'
    RATE_CLASS_COL = 'C'

    EXPECTED_SHEET_TITLES = [
        'KY',
        'MD',
        'NJ',
        'NY',
        'OH',
        'PA',
        'CheatSheet',
    ]
    EXPECTED_CELLS = list(chain.from_iterable([
            (sheet, 2, 2, 'Pricing Date'),
            (sheet, 3, 2, 'Valid Thru'),
            (sheet, 5, 0, 'LDC'),
            (sheet, 5, 1, 'Customer Type'),
            (sheet, 5, 2, 'RateClass'),
            (sheet, 5, 3, 'Annual Usage Tier'),
            (sheet, 5, 4, '(UOM)|(Zone)'),
    ] for sheet in ['KY', 'MD', 'NJ', 'NY', 'OH', 'PA']))

    date_getter = SimpleCellDateGetter('PA', 2, 3, None)
    # TODO: include validity time like "4 PM EPT" in the date

    def _extract_volume_range(self, sheet, row, col):
        below_regex = r'Below ([\d,]+) ccf/therms'
        normal_regex = r'([\d,]+) to ([\d,]+) ccf/therms'
        try:
            low, high = self.reader.get_matches(sheet, row, col, normal_regex,
                                                (parse_number, parse_number))
            if low > 0 :
                low -= 1
        except ValidationError:
            high = self.reader.get_matches(sheet, row, col, below_regex,
                                           parse_number)
            low = 0
        return low, high
    # TODO: can't use superclass method here because there's more than one
    # regex to use, with different behavior for each one.

    def _extract_quotes(self):
        for sheet in ['KY', 'MD', 'NJ', 'NY', 'OH', 'PA']:

            zone = self.reader.get(sheet, 5, 'E', basestring)
            if zone == 'Zone':
                term_start_col = 7
                term_end_col = 29
            else:
                term_start_col = 6
                term_end_col = 28

            for row in xrange(self.RATE_START_ROW,
                              self.reader.get_height(sheet) + 1):
                utility = self.reader.get(sheet, row, self.UTILITY_COL,
                                          (basestring, type(None)))
                if utility is None:
                    continue

                ldc = self.reader.get(sheet, row, self.LDC_COL,
                                      (basestring, type(None)))
                customer_type = self.reader.get(
                    sheet, row, self.CUSTOMER_TYPE_COL, (basestring, type(None)))
                rate_class = self.reader.get(sheet, row, self.RATE_CLASS_COL,
                                             (basestring, type(None)))
                rate_class_alias = '-'.join([ldc, customer_type, rate_class])
                rate_class_ids = self.get_rate_class_ids_for_alias(
                    rate_class_alias)

                min_volume, limit_volume = self._extract_volume_range(
                    sheet, row, self.VOLUME_RANGE_COL)

                for term_col in self.reader.column_range(term_start_col,
                                                         term_end_col, 7):
                    term = self.reader.get_matches(
                        sheet, self.TERM_HEADER_ROW, term_col,
                        '(\d+) Months Beginning in:', int)

                    for i in self.reader.column_range(term_col, term_col + 5):
                        start_from = self.reader.get(sheet, self.HEADER_ROW,
                                                     i, (type(None),datetime))
                        if start_from is None:
                            continue

                        start_until = date_to_datetime(
                            (Month(start_from) + 1).first)
                        price = self.reader.get(sheet, row, i,
                                                (float, type(None)))
                        # some cells are blank
                        # TODO: test spreadsheet does not include this
                        if price is None:
                            continue

                        for rate_class_id in rate_class_ids:
                            quote = MatrixQuote(
                                start_from=start_from, start_until=start_until,
                                term_months=term, valid_from=self._valid_from,
                                valid_until=self._valid_until,
                                min_volume=min_volume,
                                limit_volume=limit_volume,
                                purchase_of_receivables=False, price=price,
                                rate_class_alias=rate_class_alias,
                                service_type='gas')
                            # TODO: rate_class_id should be determined automatically
                            # by setting rate_class
                            quote.rate_class_id = rate_class_id
                            yield quote

