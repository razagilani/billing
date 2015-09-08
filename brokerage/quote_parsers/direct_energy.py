from tablib import formats

from brokerage.quote_parser import _assert_true, QuoteParser, \
    excel_number_to_datetime
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class DirectEnergyMatrixParser(QuoteParser):
    """Parser for Direct Energy spreadsheet.
    """
    FILE_FORMAT = formats.xls

    HEADER_ROW = 51
    VOLUME_RANGE_ROW = 51
    QUOTE_START_ROW = 52
    STATE_COL = 'B'
    UTILITY_COL = 'C'
    RATE_CLASS_COL = 'E'
    SPECIAL_OPTIONS_COL = 'F'
    TERM_COL = 'H'
    PRICE_START_COL = 8
    PRICE_END_COL = 13

    EXPECTED_SHEET_TITLES = [
        'Daily Matrix Price',
    ]
    EXPECTED_CELLS = [
        (0, 1, 0, 'Direct Energy HQ - Daily Matrix Price Report'),
        (0, HEADER_ROW, 0, 'Contract Start Month'),
        (0, HEADER_ROW, 1, 'State'),
        (0, HEADER_ROW, 2, 'Utility'),
        (0, HEADER_ROW, 3, 'Zone'),
        (0, HEADER_ROW, 4, r'Rate Code\(s\)'),
        (0, HEADER_ROW, 5, 'Product Special Options'),
        (0, HEADER_ROW, 6, 'Billing Method'),
        (0, HEADER_ROW, 7, 'Term'),
    ]
    DATE_CELL = (0, 3, 0, 'as of (\d+/\d+/\d+)')

    EXPECTED_ENERGY_UNIT = unit_registry.MWh

    def _extract_quotes(self):
        volume_ranges = self._extract_volume_ranges_horizontal(
            0, self.VOLUME_RANGE_ROW, self.PRICE_START_COL, self.PRICE_END_COL,
            r'(?P<low>\d+)\s*-\s*(?P<high>\d+)', fudge_high=True,
            fudge_block_size=5)

        for row in xrange(self.QUOTE_START_ROW, self._reader.get_height(0)):
            # TODO use time zone here
            start_from = excel_number_to_datetime(
                self._reader.get(0, row, 0, (int, float)))
            start_until = date_to_datetime((Month(start_from) + 1).first)
            term_months = self._reader.get(0, row, self.TERM_COL, (int, float))

            rate_class = self._reader.get(0, row, self.RATE_CLASS_COL,
                                               basestring)
            state = self._reader.get(0, row, self.STATE_COL, basestring)
            utility = self._reader.get(0, row, self.UTILITY_COL, basestring)
            rate_class_alias = '-'.join([state, utility, rate_class])
            rate_class_ids = self.get_rate_class_ids_for_alias(rate_class_alias)

            special_options = self._reader.get(0, row, self.SPECIAL_OPTIONS_COL,
                                               basestring)
            _assert_true(special_options in ['', 'POR', 'UCB', 'RR'])

            for col in xrange(self.PRICE_START_COL, self.PRICE_END_COL + 1):
                min_vol, max_vol = volume_ranges[col - self.PRICE_START_COL]
                price = self._reader.get(0, row, col, (int, float)) / 1000.
                for rate_class_id in rate_class_ids:
                    quote = MatrixQuote(
                        start_from=start_from, start_until=start_until,
                        term_months=term_months, valid_from=self._valid_from,
                        valid_until=self._valid_until,
                        min_volume=min_vol, limit_volume=max_vol,
                        rate_class_alias=rate_class_alias,
                        purchase_of_receivables=(special_options == 'POR'),
                        price=price)
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote
