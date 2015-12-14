import calendar
from datetime import datetime, time

import re
from tablib import formats

from brokerage.pdf_reader import PDFReader
from brokerage.quote_parser import QuoteParser, SpreadsheetReader, \
    StartEndCellDateGetter
from brokerage.validation import _assert_true
from core.exceptions import ValidationError
from core.model.model import GAS
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class VolunteerMatrixParser(QuoteParser):
    NAME = 'volunteer'
    reader = PDFReader(tolerance=40)

    EXPECTED_CELLS = [
        #(1, 581.94832, 241.85, 'COLUMBIA GAS of OHIO \(COH\)'),
        #(1, 538.51792, 189, 'Prices Effective for Week of:'),
        #(1, 569, 265, 'Indicative Price Offers'),
        #(1, 538, 189,  'Prices Effective for Week of:'),
        #(1, 549, 329,  'From:'), # TODO broken
        (1, 549, 391,  'To:'),
        #(1, 539, 470,  'Start\nMonth'), # TODO broken
        # TODO broken on "DTE" file
        # (1, 509, 172,  'Fixed(\s+Variable\*\*)?'),
        # (1, 509, 314,  'Fixed(\s+Variable\*\*)?'),
        # (1, 509, 455,  'Fixed(\s+Variable\*\*)?'),
        (1, 509, 70,  'PRICING LEVEL\n250-6,000 Mcf\*'),
        # refer to volume ranges, i think (below, between, and above the 2
        # numbers in the top left cell of the table) TODO: confirm
        #(1, 477, 70,  'PREMIUM'), # TODO: broken
        # (1, 455, 70,  'MARKET MID'), TODO: broken
        (1, 422, 70, 'MARKET ULTRA'),
    ]

    START_ROW, START_COL = (539, 521)
    PRICE_ROWS = [477, 455, 422]
    TERM_ROW = 520
    TERM_COLS = [189, 324, 465]

    # prices (in the "Fixed" column) are a little bit right of the term even
    # though they look left, because "$" is a different text element
    PRICE_COLS = [200, 341, 482]

    date_getter = StartEndCellDateGetter(1, 538, 319, 538, 373, '(\d+/\d+/\d+)')
    EXPECTED_ENERGY_UNIT = unit_registry.Mcf

    # very tricky: this is usually all caps, except
    # "COLUMBIA GAS of OHIO (COH)" which has a lowercase "of". also, sometimes
    # "\nIndicative Price Offers" is appended to the end, while other times
    # that is a completely separate element that we must avoid matching instead
    # of the utility name. in some cases only the length distinguishes it.
    UTILITY_NAME_PATTERN = re.compile('^([A-Z\(\) of]{10,50}).*',
                                      flags=re.DOTALL)

    def _extract_quotes(self):
        # set global vertical and horizontal offset for this file based on the
        # position of the "PRICING LEVEL" box in this file relative to where
        # it was in the "Exchange_COH_2015\ 12-7-15.pdf" file.
        # this is pretty messy but it allows enough tolerance of varying
        # positions that the same code can be used to parse all of
        # Volunteer's PDF files.
        # if this is a common thing in PDF formats, move it into PDFReader by
        # making PDFReader calibrate its coordinates according to the
        # position of a certain element.
        pricing_level_y, pricing_level_x = \
            self._reader.find_element_coordinates(1, 0, 0, 'PRICING LEVEL.*')
        self._reader.offset = (pricing_level_y - 509, pricing_level_x - 70)

        # utility name is the only rate class alias field.
        # getting this using the same code for every file is a lot harder than
        # it seems at first. here we pick the closest field within tolerance
        # of the given coordinates whose text matches the big ugly regex
        # defined above.
        rate_class_alias = self._reader.get_matches(
            1, 581, 241, self.UTILITY_NAME_PATTERN, str, tolerance=50)

        # TODO maybe target unit shound be different?
        low, high = self._extract_volume_range(
            1, 509, 70, r'PRICING LEVEL\n(?P<low>\d+)-(?P<high>[\d,r]+) Mcf.*',
            expected_unit=unit_registry.Mcf, target_unit=unit_registry.ccf)

        start_month_name, start_year = self._reader.get_matches(
            1, self.START_ROW, self.START_COL, '(\w+)-(\d+)', (str, int))
        start_month = next(i for i, abbr in enumerate(calendar.month_abbr)
                           if abbr == start_month_name)
        start_from = datetime(start_year, start_month, 1)
        start_until = date_to_datetime((Month(start_from) + 1).first)

        for row, (min_vol, limit_vol) in zip(
                self.PRICE_ROWS, [(0, low), (low, high), (high, None)]):
            for price_col, term_col in zip(self.PRICE_COLS, self.TERM_COLS):
                term = self._reader.get_matches(
                    1, self.TERM_ROW, term_col, r'Term-(\d+) Month', int)
                #price = float(self._reader.get(1, row, price_col, '.*'))
                price = self._reader.get_matches(1, row, price_col,
                                                 '(\d*\.\d+)', float)
                rate_class_ids = self.get_rate_class_ids_for_alias(
                    rate_class_alias)
                for rate_class_id in rate_class_ids:
                    quote = MatrixQuote(
                        start_from=start_from, start_until=start_until,
                        term_months=term, valid_from=self._valid_from,
                        valid_until=self._valid_until, min_volume=min_vol,
                        limit_volume=limit_vol,
                        rate_class_alias=rate_class_alias,
                        purchase_of_receivables=False, price=price,
                        service_type=GAS, file_reference='%s %s,%s,%s' % (
                            self.file_name, 1, row, price_col))
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote



