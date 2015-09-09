from datetime import datetime

from tablib import formats

from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import QuoteParser
from util.units import unit_registry


class MajorEnergyMatrixParser(QuoteParser):
    """Parser for Major Energy spreadsheet.
    """
    FILE_FORMAT = formats.xlsx

    HEADER_ROW = 14
    QUOTE_START_ROW = 15
    START_COL = 'B'
    TERM_COL = 'C'
    STATE_COL = 'D'
    UTILITY_COL = 'E'
    ZONE_COL = 'F'
    PRICE_START_COL = 6
    PRICE_END_COL = 9

    # beware of hidden sheet that contains similar data. "Matrix" is the
    # visible one
    EXPECTED_SHEET_TITLES = ['Map - Info', 'Matrix']
    SHEET = 'Matrix'
    EXPECTED_CELLS = [
        (SHEET, 3, 'B', 'Effective:'),
        (SHEET, 5, 'B', 'Start'),
        (SHEET, 5, 'C', 'State'),
        (SHEET, 5, 'D', 'Utility'),
        (SHEET, 5, 'E', 'Zone'),
        (SHEET, 5, 'F', 'Usage'),
        (SHEET, 5, 'G', 'Agent Fee'),
        (SHEET, 11, 'B', 'GRT/SUT/POR Included where applicable'),
        (SHEET, 13, 'G', 'Annual KWH Usage Tier'),
    ]
    VALIDITY_DATE_CELL = (SHEET, 3, 'C', None)
    VALIDITY_INCLUSIVE_END_CELL = (SHEET, 3, 'E', None)

    # spreadsheet says "kWh usage tier" but the numbers are small, so they
    # probably are MWh
    EXPECTED_ENERGY_UNIT = unit_registry.MWh

    def _extract_quotes(self):
        # note: these are NOT contiguous. the first two are "0-74" and
        # "75-149" but they are contiguous after that. for now, assume they
        # really mean what they say.
        volume_ranges = [
            self._extract_volume_range(self.SHEET, self.HEADER_ROW, col,
                                       r'(?P<low>\d+)\s*-\s*(?P<high>\d+)',
                                       unit_registry.MWh, unit_registry.kWh)
            for col in xrange(self.PRICE_START_COL, self.PRICE_END_COL + 1)]

        for row in xrange(self.QUOTE_START_ROW,
                         self._reader.get_height(self.SHEET) + 1):
            # TODO use time zone here
            start_from = self._reader.get(self.SHEET, row, self.START_COL,
                                          datetime)
            start_until = date_to_datetime((Month(start_from) + 1).first)
            term_months = self._reader.get(self.SHEET, row, self.TERM_COL, int)

            utility = self._reader.get(self.SHEET, row, self.UTILITY_COL,
                                       basestring)
            state = self._reader.get(self.SHEET, row, self.STATE_COL,
                                     basestring)
            rate_class_alias = '-'.join([state, utility])
            rate_class_ids = self.get_rate_class_ids_for_alias(rate_class_alias)

            for col in xrange(self.PRICE_START_COL, self.PRICE_END_COL + 1):
                min_vol, max_vol = volume_ranges[col - self.PRICE_START_COL]
                price = self._reader.get(self.SHEET, row, col, (int, float))
                for rate_class_id in rate_class_ids:
                    quote = MatrixQuote(
                        start_from=start_from, start_until=start_until,
                        term_months=term_months, valid_from=self._valid_from,
                        valid_until=self._valid_until,
                        min_volume=min_vol, limit_volume=max_vol,
                        purchase_of_receivables=False,
                        rate_class_alias=rate_class_alias, price=price)
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote