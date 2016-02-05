from itertools import chain
from datetime import datetime, timedelta
from brokerage.reader import parse_number

from tablib import formats

from brokerage.quote_parser import QuoteParser
from brokerage.reader import parse_number
from brokerage.spreadsheet_reader import SpreadsheetReader
from core.exceptions import ValidationError
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote


__author__ = 'Bill Van Besien'

class USGEElectricMatrixParser(QuoteParser):
    """Parser for USGE spreadsheet. This one has energy along the rows and
    time along the columns.
    """
    NAME = 'usgeelectic'
    reader = SpreadsheetReader(formats.xlsx)

    TERM_HEADER_ROW = 4
    HEADER_ROW = 5
    RATE_START_ROW = 6
    UTILITY_COL = 0
    VOLUME_RANGE_COL = 3
    RATE_END_COL = 11
    TERM_START_COL = 6
    TERM_END_COL = 28
    LDC_COL = 'A'
    CUSTOMER_TYPE_COL = 'B'
    RATE_CLASS_COL = 'C'

    EXPECTED_SHEET_TITLES = [
        'CT',
        'IL',
        'MA',
        'MD',
        'NJ',
        'NY',
        'OH',
        'PA',
        #'CheatSheet',
    ]

    EXPECTED_CELLS = list(chain.from_iterable([
            (sheet, 2, 2, 'Pricing Date'),
            (sheet, 3, 2, 'Valid Thru'),
            (sheet, 5, 0, 'LDC'),
            (sheet, 5, 1, 'Customer Type'),
            (sheet, 5, 2, 'RateClass'),
            (sheet, 5, 3, 'Annual Usage Tier'),
            #(sheet, 5, 4, '(Zone|$^'),
        ] for sheet in [s for s in EXPECTED_SHEET_TITLES if s != 'CheatSheet']))

    def _extract_volume_range(self, sheet, row, col):
        below_regex = r'Below ([\d,]+) [kK][wW][hH]'
        normal_regex = r'([\d,]+)-([\d,]+) [kK][wW][hH]'
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
        for sheet in self.EXPECTED_SHEET_TITLES:
            # Sometimes this can be None so we can't force it to expect a basestring
            zone = self.reader.get(sheet, 5, 'E', object)
            if zone == 'Zone':
                zone_col = 'E'
                term_start_col = 6
                term_end_col = self.reader.get_width(sheet)
            else:
                zone_col = None
                term_start_col = 5
                term_end_col = self.reader.get_width(sheet)

            # This is the date at the top of the document in each spreadsheet
            valid_from = self.reader.get(sheet, 2, 'D', datetime)
            valid_until = valid_from + timedelta(days=1)

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
                if zone_col:
                    zone = self.reader.get(sheet, row, zone_col, basestring)
                else:
                    zone = ""
                rate_class_alias = 'USGE-electric-%s' % '-'.join([ldc, customer_type, rate_class, zone])
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
                                term_months=term, valid_from=valid_from,
                                valid_until=valid_until,
                                min_volume=min_volume,
                                limit_volume=limit_volume,
                                purchase_of_receivables=False, price=price,
                                rate_class_alias=rate_class_alias,
                                service_type='electric',
                                file_reference='%s %s,%s,%s' % (
                                    self.file_name, sheet, row, i))
                            # TODO: rate_class_id should be determined automatically
                            # by setting rate_class
                            quote.rate_class_id = rate_class_id
                            print quote
                            yield quote
