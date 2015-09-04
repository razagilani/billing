from datetime import datetime, timedelta

from tablib import formats

from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import QuoteParser, _assert_equal, _assert_true


class ConstellationMatrixParser(QuoteParser):
    FILE_FORMAT = formats.xlsx

    HEADER_ROW = 4
    VOLUME_RANGE_ROW = 5
    QUOTE_START_ROW = 6
    STATE_COL = 'A'
    UTILITY_COL = 'B'
    TERM_COL = 'C'
    START_FROM_START_COL = 3
    DATE_COL = 'K'
    PRICE_START_COL = 3
    PRICE_END_COL = 38

    EXPECTED_SHEET_TITLES = [
        'SMB Cost+ Matrix',
    ]
    EXPECTED_CELLS = [
        (0, 1, 0, 'Fixed Fully Bundled'),
        (0, 1, 'I', 'Small Business Cost\+ Pricing'),
        (0, 2, 'A', 'Matrix pricing for customers up to 1000 Ann MWh'),
        (0, 4, 'A', 'ISO'),
        (0, 4, 'B', 'Utility'),
        (0, 4, 'C', 'Term'),
    ]
    DATE_CELL = (0, 2, DATE_COL, None)

    def _extract_volume_range(self, row, col):
        regex = r'(\d+)\s*-\s*(\d+)\s+MWh'
        low, high = self._reader.get_matches(0, row, col, regex, (float, float))
        # low value is really 1 higher than it should be in cases like
        # "151-300" preceded by "0-150"
        _assert_true(low == 0 or low % 10 == 1)
        if low % 10 == 1:
            low -= 1
        return low * 1000, high * 1000

    def _extract_quotes(self):
        volume_ranges = [self._extract_volume_range(self.VOLUME_RANGE_ROW, col)
                         for col in xrange(self.PRICE_START_COL,
                                           self.PRICE_END_COL + 1)]
        # # volume ranges should be contiguous or restarting at 0
        for i, vr in enumerate(volume_ranges[:-1]):
            next_vr = volume_ranges[i + 1]
            if next_vr[0] != 0:
                _assert_equal(vr[1], next_vr[0])

        for row in xrange(self.QUOTE_START_ROW, self._reader.get_height(0)):
            utility = self._reader.get(0, row, self.UTILITY_COL,
                                       (basestring, type(None), datetime))
            if utility is None:
                continue
            elif isinstance(utility, datetime):
                # repeat of the top of the spreadsheet
                _assert_equal('Fixed Fully Bundled',
                              self._reader.get(0, row, 0, basestring))
                _assert_equal('Small Business Cost+ Pricing',
                              self._reader.get(0, row, 'I', basestring))
                _assert_equal(self._valid_from,
                              self._reader.get(0, row + 1,
                                               self.DATE_COL, datetime))
                continue
            elif utility == 'Utility':
                # repeat of the header row
                continue
            term_months = self._reader.get(0, row, self.TERM_COL, (int, float))

            # there's no fine-grained classification of customers
            rate_class_alias = utility
            rate_class_ids = self.get_rate_class_ids_for_alias(rate_class_alias)

            for col in xrange(self.PRICE_START_COL, self.PRICE_END_COL + 1):
                price = self._reader.get(0, row, col,
                                         (int, float, type(None)))
                # skip blank cells. also, many cells that look blank in Excel
                #  actually have negative prices, such as (35,27) (in
                # tablib's numbering) where the price is -0.995
                if price == None or price < 0:
                    continue

                # the 'start_from' date is in the first cell of the group of
                # 4 that started at a multiple of 4 columns away from
                # 'START_FROM_START_COL'
                start_from_col = self.START_FROM_START_COL + (
                    col - self.START_FROM_START_COL) / 4 * 4
                start_from = self._reader.get(
                    0, self.HEADER_ROW, start_from_col, datetime)
                start_until = date_to_datetime((Month(start_from) + 1).first)

                min_vol, max_vol = volume_ranges[col - self.PRICE_START_COL]
                for rate_class_id in rate_class_ids:
                    quote = MatrixQuote(
                        start_from=start_from, start_until=start_until,
                        term_months=term_months, valid_from=self._valid_from,
                        valid_until=self._valid_until,
                        min_volume=min_vol, limit_volume=max_vol,
                        rate_class_alias=rate_class_alias,
                        purchase_of_receivables=False, price=price)
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote
