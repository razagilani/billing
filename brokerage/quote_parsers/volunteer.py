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


    # used for validation and setting PDFReader offset to account for varying
    # positions of elements in each file, as well as extracting the volume
    # ranges
    PRICING_LEVEL_PATTERN = \
        'PRICING LEVEL\n(?P<low>\d+)-(?P<high>[\d,r]+) Mcf.*'

    # very tricky: this is usually all caps, except
    # "COLUMBIA GAS of OHIO (COH)" which has a lowercase "of". also, sometimes
    # "\nIndicative Price Offers" is appended to the end, while other times
    # that is a completely separate element that we must avoid matching instead
    # of the utility name. in some cases only the length distinguishes it.
    UTILITY_NAME_PATTERN = re.compile('^([A-Z\(\) of]{10,50}).*',
                                      flags=re.DOTALL)

    # only these two have positions consistent enough to use the same
    # coordinates for every file
    EXPECTED_CELLS = [
        (1, 509, 70,  PRICING_LEVEL_PATTERN),
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

    def _after_load(self):
        # set global vertical and horizontal offset for each file based on the
        # position of the "PRICING LEVEL" box in that file relative to where
        # it was in the "Exchange_COH_2015\ 12-7-15.pdf" file. this may be
        # ugly but it allows enough tolerance of varying positions that the
        # same code can be used to parse all of Volunteer's PDF files.
        self._reader.set_offset_by_element_regex(
            self.PRICING_LEVEL_PATTERN, element_x=70, element_y=509)

    def _validate(self):
        # these can't go in EXPECTED_CELLS because their position varies too
        # much to use fixed coordinates for every file. instead, use the
        # fuzzy position behavior in PDFReader.get_matches.
        for page_number, y, x, regex in [
            (1, 569, 265, re.compile('.*Indicative Price Offers', re.DOTALL)),
            (1, 549, 391, 'To:'),
            (1, 549, 329, 'From:'),
            (1, 539, 470, 'Start\nMonth'),
            (1, 538, 189, 'Prices Effective for Week of:'),
            (1, 538, 189, 'Prices Effective for Week of:'),
            (1, 509, 455, 'Fixed(?:\s+Variable\*\*)?'),
            (1, 509, 314, 'Fixed(?:\s+Variable\*\*)?'),
            (1, 509, 172, 'Fixed(?:\s+Variable\*\*)?'),
            (1, 477, 70, 'PREMIUM'),
            (1, 455, 70, 'MARKET MID'),
        ]:
            # types argument is [] because there are no groups; this is just
            # to check for matches rather than extract data
            self._reader.get_matches(page_number, y, x, regex, [], tolerance=40)

    def _extract_quotes(self):
        # utility name is the only rate class alias field.
        # getting this using the same code for every file is a lot harder than
        # it seems at first. here we pick the closest field within tolerance
        # of the given coordinates whose text matches the big ugly regex
        # defined above.
        rate_class_alias = self._reader.get_matches(
            1, 581, 241, self.UTILITY_NAME_PATTERN, str, tolerance=50)

        # TODO maybe target unit shound be different?
        low, high = self._extract_volume_range(
            1, 509, 70, self.PRICING_LEVEL_PATTERN,
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



