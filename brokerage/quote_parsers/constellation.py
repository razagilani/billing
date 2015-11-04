from datetime import datetime

from tablib import formats

from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import QuoteParser, _assert_equal, \
    SimpleCellDateGetter, SpreadsheetReader, FileNameDateGetter
from util.units import unit_registry


class ConstellationMatrixParser(QuoteParser):
    NAME = 'constellation'

    FILE_FORMAT = formats.xlsx

    START_FROM_ROW = 6
    VOLUME_RANGE_ROW = 8
    QUOTE_START_ROW = 10
    STATE_COL = 'B'
    UDC_COL = 'C'
    TERM_COL = 'D'
    # must convert column letter to number to do arithmetic with it
    PRICE_START_COL = SpreadsheetReader.col_letter_to_index('E')
    DATE_COL = 'E'
    PRICE_END_COL = 'BO'

    # ignore hidden sheet that is the same as the old format!
    EXPECTED_SHEET_TITLES = [ 'SMB Cost+ Matrix_Data', ]
    SHEET = 2 # title doesn't work for some reason
    EXPECTED_CELLS = [
        (SHEET, 6, STATE_COL, 'STATE'),
        (SHEET, 6, UDC_COL, 'UDC'),
        (SHEET, 6, TERM_COL, 'TERM'),
    ]
    EXPECTED_ENERGY_UNIT = unit_registry.MWh

    date_getter = FileNameDateGetter(
        r'.*Fully Bundled_(\d\d_\d\d_\d\d\d\d)\.xlsm')

    def _extract_quotes(self):
        volume_ranges = self._extract_volume_ranges_horizontal(
                self.SHEET, self.VOLUME_RANGE_ROW, self.PRICE_START_COL,
            self.PRICE_END_COL, r'(?P<low>\d+)\s*-\s*(?P<high>\d+)\s+MWh',
            allow_restarting_at_0=True, fudge_low=True, fudge_high=True,
            fudge_block_size=5)

        for row in xrange(self.QUOTE_START_ROW,
                          self._reader.get_height(self.SHEET)):
            state = self._reader.get(self.SHEET, row, self.STATE_COL,
                                     basestring)
            # "UDC" and "term" can both be blank; if so, skip the row
            udc = self._reader.get(self.SHEET, row, self.UDC_COL,
                                   (basestring, type(None)))
            if udc is None:
                continue
            term_months = self._reader.get(self.SHEET, row, self.TERM_COL,
                                           (int, type(None)))
            if term_months is None:
                continue

            rate_class_alias = '-'.join([state, udc])
            rate_class_ids = self.get_rate_class_ids_for_alias(rate_class_alias)

            for col in self._reader.column_range(self.PRICE_START_COL,
                                                 self.PRICE_END_COL):
                price = self._reader.get(self.SHEET, row, col,
                                         (int, float, type(None)))
                # skip blank cells. also, many cells that look blank in Excel
                #  actually have negative prices, such as (35,27) (in
                # tablib's numbering) where the price is -0.995
                if price == None or price < 0:
                    continue

                # the 'start_from' date is in the first cell of the group of
                # 7 that started at a multiple of 7 columns away from
                # 'START_FROM_START_COL'
                start_from_col = self.PRICE_START_COL + (
                    col - self.PRICE_START_COL) / 7 * 7
                start_from = self._reader.get(
                    self.SHEET, self.START_FROM_ROW, start_from_col, datetime)
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
