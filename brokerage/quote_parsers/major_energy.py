from datetime import datetime

from tablib import formats

from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import QuoteParser, StartEndCellDateGetter
from util.units import unit_registry


class MajorEnergyElectricSheetParser(QuoteParser):
    """Used by MajorEnergyMatrixParser for handling only the sheet that contains
    electricity quotes.
    """
    FILE_FORMAT = formats.xlsx

    # electric-specific coordinates
    HEADER_ROW = 14
    QUOTE_START_ROW = 15
    START_COL = 'B'
    TERM_COL = 'C'
    STATE_COL = 'D'
    UTILITY_COL = 'E'
    ZONE_COL = 'F'
    PRICE_START_COL = 6
    PRICE_END_COL = 9

    SHEET = 'Commercial E'
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

    # spreadsheet says "kWh usage tier" but the numbers are small, so they
    # probably are MWh
    EXPECTED_ENERGY_UNIT = unit_registry.MWh

    date_getter = StartEndCellDateGetter(SHEET, 3, 'C', 3, 'E', None)

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

            utility = self._reader.get(self.SHEET, row, self.UTILITY_COL,
                                       basestring)
            state = self._reader.get(self.SHEET, row, self.STATE_COL,
                                     basestring)
            rate_class_alias_parts = ['electric', state, utility]
            zone = self._reader.get(self.SHEET, row, self.ZONE_COL,
                                    (basestring, type(None)))
            if zone is not None:
                rate_class_alias_parts.append(zone)
            rate_class_alias = '-'.join(rate_class_alias_parts)
            rate_class_ids = self.get_rate_class_ids_for_alias(rate_class_alias)

            term_months = self._reader.get(self.SHEET, row, self.TERM_COL, int)

            for col in xrange(self.PRICE_START_COL, self.PRICE_END_COL + 1):
                # for gas, term is different for each column
                # (this could be done one instead of in a loop)
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


class MajorEnergyGasSheetParser(QuoteParser):
    """Used by MajorEnergyMatrixParser for handling only the sheet that contains
    gas quotes.
    """
    FILE_FORMAT = formats.xlsx

    HEADER_ROW = 7
    QUOTE_START_ROW = 8
    START_COL = 'B'
    STATE_COL = 'C'
    UTILITY_COL = 'D'
    PRICE_START_COL = 'E'
    PRICE_END_COL = 'G'

    SHEET = 'NG R & SC'
    EXPECTED_CELLS = [
        (SHEET, 3, 'B', 'Effective:'),
        (SHEET, 7, 'B', 'Start'),
        (SHEET, 7, 'C', 'State'),
        (SHEET, 7, 'D', 'Utility'),
        (SHEET, 5, 'B', 'GRT/SUT/POR Included where applicable'),
    ]

    date_getter = StartEndCellDateGetter(SHEET, 3, 'C', 3, 'E', None)

    def _extract_quotes(self):
        for row in xrange(self.QUOTE_START_ROW,
                         self._reader.get_height(self.SHEET) + 1):
            # todo use time zone here
            start_from = self._reader.get(self.SHEET, row, self.START_COL,
                                          datetime)
            start_until = date_to_datetime((Month(start_from) + 1).first)
            utility = self._reader.get(self.SHEET, row, self.UTILITY_COL,
                                       basestring)
            state = self._reader.get(self.SHEET, row, self.STATE_COL,
                                     basestring)
            rate_class_alias_parts = ['gas', state, utility]
            rate_class_alias = '-'.join(rate_class_alias_parts)
            rate_class_ids = self.get_rate_class_ids_for_alias(rate_class_alias)

            for col in self._reader.column_range(self.PRICE_START_COL,
                                                 self.PRICE_END_COL):
                # for gas, term is different for each column
                # (this could be done one instead of in a loop)
                term_months = self._reader.get_matches(
                    self.SHEET, self.HEADER_ROW, col, '(\d+) Months', int)
                price = self._reader.get(self.SHEET, row, col,
                                         (int, float, type(None)))
                # skip blank cells
                if price is None:
                    continue

                for rate_class_id in rate_class_ids:
                    quote = MatrixQuote(
                        start_from=start_from, start_until=start_until,
                        term_months=term_months, valid_from=self._valid_from,
                        valid_until=self._valid_until,
                        min_volume=None, limit_volume=None,
                        purchase_of_receivables=False,
                        rate_class_alias=rate_class_alias, price=price)
                    # todo: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote


class MajorEnergyMatrixParser(QuoteParser):
    """Parser for Major Energy spreadsheet. This has two sheets for electric
    and gas quotes, which have so little overlap that they are implemented in
    separate classes.

    This design may not be very good because it loads the same file multiple
    times, and because there is still some code duplication between the two
    classes that should be eliminated. But it works well enough.
    """
    FILE_FORMAT = formats.xlsx

    # only validation that applies to the entire file goes in this class.
    # beware of hidden sheet that contains similar data
    EXPECTED_SHEET_TITLES = ['Commercial E', 'NG R & SC']

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self._electric_parser = MajorEnergyElectricSheetParser(*args, **kwargs)
        self._gas_parser = MajorEnergyGasSheetParser(*args, **kwargs)

    def load_file(self, *args, **kwargs):
        super(self.__class__, self).load_file(*args, **kwargs)
        self._electric_parser.load_file(*args, **kwargs)
        self._gas_parser.load_file(*args, **kwargs)

    def _validate(self):
        self._electric_parser.validate()
        self._gas_parser.validate()

    def _extract_quotes(self):
        for quote in self._electric_parser.extract_quotes():
            yield quote
        for quote in self._gas_parser.extract_quotes():
            yield quote
