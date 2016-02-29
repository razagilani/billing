import calendar
import re
from datetime import datetime

from tablib import formats

from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import QuoteParser, SimpleCellDateGetter
from brokerage.spreadsheet_reader import SpreadsheetReader
from brokerage.spreadsheet_reader import TabulaConverter
from brokerage.validation import ValidationError
from core.model.model import GAS
from util.dateutils import date_to_datetime
from util.monthmath import Month
from util.units import unit_registry


class GEEGasNYParser(QuoteParser):
    NAME = 'geegasny'
    reader = SpreadsheetReader(formats.csv)

    SHEET = 0

    # column of rate class alias, which sometimes also has date text appended
    # to the end
    RCA_COL = 'A'

    # column containing a start date string when not appended to the end of
    # RCA_COL
    START_COL = 'B'

    # number of columns to be used for price numbers (and some term length
    # numbers). the start of this block of columns may vary, and some columns
    # may be empty, but we only care about the combined text of all of them.
    PRICE_COLS_MAX_WIDTH = 8

    HEADER_ROW = 4
    TERM_ROW = 5

    # if column A matches any of these, the row does not contain quotes
    SKIP_PATTERNS = [
       '.*Start is for Renewal accounts.*',
       'Natural Gas Rack Rates',
        r'.*(\d+/\d+/\d+).*',
        'Utility Load Type.*',
        r'^\w*$',
    ]

    date_getter = SimpleCellDateGetter(SHEET, 2, 'A', '(.*)')

    # TODO
    EXPECTED_ENERGY_UNIT = 10 * unit_registry.therm

    def _preprocess_file(self, quote_file, file_name):
        return TabulaConverter().convert_file(quote_file, file_name)

    # TODO move to Reader
    def _get_joined_row_text(self, sheet, columns, row):
        return ''.join(self.reader.get(
            sheet, row, col, basestring) for col in columns)

    def _extract_quotes(self):
        for row in xrange(self.TERM_ROW + 1,
                          self.reader.get_height(self.SHEET)):
            # skip row if it is known not to contain quotes
            if any(re.match(
                    pattern, self.reader.get(self.SHEET, row, 'A', basestring))
                   for pattern in self.SKIP_PATTERNS):
                continue

            # extract rate class alias and date from columns A and/or B
            try:
                # in rows 5-47, rate class alias and start date are smashed
                # together in the same column
                rca, month_name, year = self.reader.get_matches(
                    self.SHEET, row, self.RCA_COL, '(.*) (\w+)-(\d\d)\s*',
                    (unicode, unicode, int))
                price_cols = self.reader.column_range('B', 'J')
            except ValidationError:
                # in rows 53-68, rate class alias and start date are in
                # separate columns, so all other columns are shifted to the
                # right by 1.
                rca = self.reader.get(self.SHEET, row, self.RCA_COL, basestring)
                month_name, year = self.reader.get_matches(
                    self.SHEET, row, self.START_COL, '(\w+)-(\d\d)\s*',
                    (unicode, int))
                price_cols = self.reader.column_range('C', 'J')

            # get start/end dates from month abbreviation + 2-digit year
            month = next(i for i, abbr in enumerate(calendar.month_abbr)
                         if abbr.lower() == month_name.lower())
            start_from = datetime(2000 + year, month, 1)
            start_until = date_to_datetime((Month(start_from) + 1).first)

            # extract term length number strings from the top row of term
            # lengths (but some term lengths are in the "Term" column,
            # an some parts of this row are column headers that can be skipped).
            # these should look like: 6, 12, 18, 24, 6, 12, 18, 24
            term_text = self._get_joined_row_text(
                self.SHEET, price_cols, self.TERM_ROW)
            terms = (s for s in term_text.split() if re.match('\d+', s))

            # a block of 4 prices matching the "terms" above, 1 term and price
            # pair (labeled "Sweet Spot"), then same thing repeated.
            # (see column arrangement in original PDF, not CSV.)
            price_and_term_strs = self._get_joined_row_text(
                self.SHEET, price_cols, row).split()
            prices_1 = price_and_term_strs[0:4]
            ss_term_1 = price_and_term_strs[4]
            ss_price_1 = price_and_term_strs[5]
            prices_2 = price_and_term_strs[6:10]
            ss_term_2 = price_and_term_strs[10]
            ss_price_2 = price_and_term_strs[11]

            # convert to appropriate types
            all_prices_and_terms = ((float(p), int(t)) for p, t in
                zip(prices_1, terms) + [(ss_price_1, ss_term_1)] +
                zip(prices_2, terms) + [(ss_price_2, ss_term_2)])

            for price, term in all_prices_and_terms:
                for rate_class_id in self.get_rate_class_ids_for_alias(rca):
                    quote = MatrixQuote(
                        start_from=start_from, start_until=start_until,
                        term_months=term, valid_from=self._valid_from,
                        valid_until=self._valid_until, rate_class_alias=rca,
                        price=price, service_type=GAS,
                        # column not included in file reference because it's
                        # hard to determine (even in intermediate CSV format)
                        file_reference='%s %s,%s' % (self.file_name, 1, row))
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote

