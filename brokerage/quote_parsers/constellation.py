from datetime import datetime

from tablib import formats

from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import QuoteParser, _assert_equal, \
    SimpleCellDateGetter
from util.units import unit_registry


class ConstellationMatrixParser(QuoteParser):
    FILE_FORMAT = formats.xlsx

    HEADER_ROW = 4
    VOLUME_RANGE_ROW = 5
    QUOTE_START_ROW = 6
    STATE_COL = 'B'
    UDC_COL = 'C'
    TERM_COL = 'C'
    START_FROM_START_COL = 3
    DATE_COL = 'E'
    # TODO: check these
    PRICE_START_COL = 3
    PRICE_END_COL = 38

    # ignore hidden sheet that is the same as the old format!
    EXPECTED_SHEET_TITLES = [ 'SMB Cost+ Matrix_Data', ]
    SHEET = 'SMB Cost+ Matrix_Data'
    EXPECTED_CELLS = [
        (SHEET, 1, 'E', 'Small Business Cost\+ Pricing \(Fully Bundled\)'),
        (SHEET, 2, 'A', 'Matrix pricing for customers up to 1000 Ann MWh'),
        (SHEET, 6, 'B', 'State'),
        (SHEET, 6, 'C', 'UDC'),
        (SHEET, 6, 'D', 'Term'),
    ]
    EXPECTED_ENERGY_UNIT = unit_registry.MWh

    date_getter = SimpleCellDateGetter(SHEET, 5, DATE_COL, None)

    def _extract_quotes(self):
        volume_ranges = self._extract_volume_ranges_horizontal(
                self.SHEET, self.VOLUME_RANGE_ROW, self.PRICE_START_COL,
            self.PRICE_END_COL, r'(?P<low>\d+)\s*-\s*(?P<high>\d+)\s+MWh',
            allow_restarting_at_0=True, fudge_low=True)

        for row in xrange(self.QUOTE_START_ROW,
                          self._reader.get_height(self.SHEET)):
            state = self._reader.get(self.SHEET, row, self.STATE_COL, basestring)
            udc = self._reader.get(self.SHEET, row, self.UDC_COL, basestring)
            # elif isinstance(utility, datetime):
            #     # repeat of the top of the spreadsheet
            #     _assert_equal('Fixed Fully Bundled',
            #                   self._reader.get(self.SHEET, row, 0, basestring))
            #     _assert_equal('Small Business Cost+ Pricing',
            #                   self._reader.get(self.SHEET, row, 'I', basestring))
            #     _assert_equal(self._valid_from,
            #                   self._reader.get(self.SHEET, row + 1,
            #                                    self.DATE_COL, datetime))
            #     continue
            term_months = self._reader.get(self.SHEET, row, self.TERM_COL,
                                           (int, float))

            rate_class_alias = '-'.join([state, udc])
            rate_class_ids = self.get_rate_class_ids_for_alias(rate_class_alias)

            for col in xrange(self.PRICE_START_COL, self.PRICE_END_COL + 1):
                price = self._reader.get(self.SHEET, row, col,
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
                    self.SHEET, self.HEADER_ROW, start_from_col, datetime)
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
