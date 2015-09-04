from itertools import chain
from datetime import datetime, timedelta

from tablib import formats

from brokerage.quote_parser import QuoteParser, _assert_true, parse_number
from exc import ValidationError
from util.dateutils import date_to_datetime, excel_number_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote


class USGEMatrixParser(QuoteParser):
    """Parser for USGE spreadsheet. This one has energy along the rows and
    time along the columns.
    """
    FILE_FORMAT = formats.xlsx

    TERM_HEADER_ROW = 4
    HEADER_ROW = 5
    RATE_START_ROW = 6
    RATE_END_ROW = 34
    UTILITY_COL = 0
    VOLUME_RANGE_COL = 3
    RATE_END_COL = 11
    TERM_START_COL = 6
    TERM_END_COL = 28
    LDC_COL = 'A'
    CUSTOMER_TYPE_COL = 'B'
    RATE_CLASS_COL = 'C'

    EXPECTED_SHEET_TITLES = [
        'KY',
        'MD',
        'NJ',
        'NY',
        'OH',
        'PA',
        'CheatSheet',
    ]
    EXPECTED_CELLS = list(chain.from_iterable([
            (sheet, 2, 2, 'Pricing Date'),
            (sheet, 3, 2, 'Valid Thru'),
            (sheet, 5, 0, 'LDC'),
            (sheet, 5, 1, 'Customer Type'),
            (sheet, 5, 2, 'RateClass'),
            (sheet, 5, 3, 'Annual Usage Tier'),
            (sheet, 5, 4, '(UOM)|(Zone)'),
    ] for sheet in ['KY', 'MD', 'NJ', 'NY', 'OH', 'PA']))

    DATE_CELL = ('PA', 2, 3, None)
    # TODO: include validity time like "4 PM EPT" in the date

    def _extract_volume_range(self, sheet, row, col):
        below_regex = r'Below ([\d,]+) ccf/therms'
        normal_regex = r'([\d,]+) to ([\d,]+) ccf/therms'
        try:
            low, high = self._reader.get_matches(sheet, row, col, normal_regex,
                                                 (parse_number, parse_number))
            if low > 0 :
                low -= 1
        except ValidationError:
            high = self._reader.get_matches(sheet, row, col, below_regex,
                                            parse_number)
            low = 0
        return low, high


    def _extract_quotes(self):
        for sheet in ['KY', 'MD', 'NJ', 'NY', 'OH', 'PA']:

            zone = self._reader.get(sheet,5,'E',basestring)
            if zone == 'Zone':
                term_start_col = 7
                term_end_col = 29
            else:
                term_start_col = 6
                term_end_col = 28

            for row in xrange(self.RATE_START_ROW,
                              self._reader.get_height(sheet) + 1):
                utility = self._reader.get(sheet, row, self.UTILITY_COL,
                                           (basestring, type(None)))
                if utility is None:
                    continue

                ldc = self._reader.get(sheet, row, self.LDC_COL,
                                       (basestring, type(None)))
                customer_type = self._reader.get(sheet, row, self.CUSTOMER_TYPE_COL,
                                                 (basestring, type(None)))
                rate_class = self._reader.get(sheet, row,self.RATE_CLASS_COL,
                (basestring, type(None)))
                rate_class_alias = '-'.join([ldc, customer_type, rate_class])

                rate_class_ids = self.get_rate_class_ids_for_alias(
                    rate_class_alias)

                min_volume, limit_volume = self._extract_volume_range(
                    sheet, row, self.VOLUME_RANGE_COL)

                for term_col in xrange(term_start_col, term_end_col + 1, 7):
                    term = self._reader.get_matches(
                        sheet, self.TERM_HEADER_ROW, term_col,
                        '(\d+) Months Beginning in:', int)

                    for i in xrange(term_col, term_col + 6):
                        start_from = self._reader.get(sheet, self.HEADER_ROW,
                                                      i, (type(None),datetime))
                        if start_from is None:
                            continue

                        start_until = date_to_datetime(
                            (Month(start_from) + 1).first)
                        price = self._reader.get(sheet, row, i,
                                                 (float, type(None)))
                        # some cells are blank
                        # TODO: test spreadsheet does not include this
                        if price is None:
                            continue

                        for rate_class_id in rate_class_ids:
                            quote = MatrixQuote(
                                start_from=start_from, start_until=start_until,
                                term_months=term, valid_from=self._valid_from,
                                valid_until=self._valid_until,
                                min_volume=min_volume,
                                limit_volume=limit_volume,
                                purchase_of_receivables=False, price=price,
                                rate_class_alias=rate_class_alias)
                            # TODO: rate_class_id should be determined automatically
                            # by setting rate_class
                            quote.rate_class_id = rate_class_id
                            yield quote


class AEPMatrixParser(QuoteParser):
    """Parser for AEP Energy spreadsheet.
    """
    FILE_FORMAT = formats.xls

    EXPECTED_SHEET_TITLES = [
        'Price Finder', 'Customer Information', 'Matrix Table-FPAI',
        'Matrix Table-Energy Only', 'PLC Load Factor Calculator', 'A1-1',
        'A1-2', 'Base', 'Base Energy Only']

    # FPAI is "Fixed-Price All-In"; we're ignoring the "Energy Only" quotes
    SHEET = 'Matrix Table-FPAI'

    EXPECTED_CELLS = [
        (SHEET, 3, 'E', 'Matrix Pricing'),
        (SHEET, 3, 'V', 'Date of Matrix:'),
        (SHEET, 4, 'V', 'Pricing Valid Thru:'),
        (SHEET, 7, 'C', r'Product: Fixed Price All-In \(FPAI\)'),
        (SHEET, 8, 'C', 'Aggregate Size Max: 1,000 MWh/Yr'),
        (SHEET, 9, 'C', r'Pricing Units: \$/kWh'),
        (SHEET, 7, 'I',
         r"1\) By utilizing AEP Energy's Matrix Pricing, you agree to follow "
         "the  Matrix Pricing Information, Process, and Guidelines document"),
        (SHEET, 8, 'I',
         r"2\) Ensure sufficient time to enroll for selected start month; "
         "enrollment times vary by LDC"),
        (SHEET, 11, 'I', "Customer Size: 0-100 Annuals MWhs"),
        (SHEET, 11, 'M', "Customer Size: 101-250 Annuals MWhs"),
        (SHEET, 11, 'Q', "Customer Size: 251-500 Annuals MWhs"),
        (SHEET, 11, 'U', "Customer Size: 501-1000 Annuals MWhs"),
        (SHEET, 13, 'C', "State"),
        (SHEET, 13, 'D', "Utility"),
        (SHEET, 13, 'E', r"Rate Code\(s\)"),
        (SHEET, 13, 'F', "Rate Codes/Description"),
        (SHEET, 13, 'G', "Start Month"),
    ]
    DATE_CELL = (SHEET, 3, 'W', None) # TODO: correct cell but value is a float
    # TODO: prices are valid until 6 PM CST = 7 PM EST according to cell
    # below the date cell

    VOLUME_RANGE_ROW = 11
    HEADER_ROW = 13
    QUOTE_START_ROW = 14
    STATE_COL = 'C'
    UTILITY_COL = 'D'
    RATE_CODES_COL = 'E'
    # TODO what is "rate code(s)" in col E?
    RATE_CLASS_COL = 'F'
    START_MONTH_COL = 'G'

    # columns for headers like "Customer Size: 101-250 Annuals MWhs"
    VOLUME_RANGE_COLS = ['I', 'M', 'Q', 'U']

    def _extract_volume_range(self, row, col):
        regex = r'Customer Size: (\d+)-(\d+) Annuals MWhs'
        low, high = self._reader.get_matches(self.SHEET, row, col, regex,
                                             (int, int))
        if low % 10 == 1:
            low -= 1
        return low, high

    def _extract_quotes(self):
        for row in xrange(self.QUOTE_START_ROW,
                          self._reader.get_height(self.SHEET)):
            state = self._reader.get(self.SHEET, row, self.STATE_COL,
                                     basestring)
            # blank line means end of sheet
            if state == '':
                continue

            utility = self._reader.get(self.SHEET, row, self.UTILITY_COL,
                                       basestring)
            state = self._reader.get(self.SHEET, row,
                                              self.STATE_COL, basestring)
            rate_codes = self._reader.get(self.SHEET, row,
                                              self.RATE_CODES_COL, basestring)
            rate_class = self._reader.get(self.SHEET, row,
                                              self.RATE_CLASS_COL, basestring)
            rate_class_alias = '-'.join([state, utility, rate_codes,rate_class])

            # TODO use time zone here
            start_from = excel_number_to_datetime(
                self._reader.get(self.SHEET, row, self.START_MONTH_COL, float))
            start_until = date_to_datetime((Month(start_from) + 1).first)

            for i, vol_col in enumerate(self.VOLUME_RANGE_COLS):
                min_volume, limit_volume = self._extract_volume_range(
                    self.VOLUME_RANGE_ROW, vol_col)

                # TODO: ugly
                try:
                    next_vol_col = self.VOLUME_RANGE_COLS[i + 1]
                except IndexError:
                    next_vol_col = 'Y'

                for col in self._reader.column_range(vol_col, next_vol_col):
                    # skip column that says "End May '18" since we don't know
                    # what contract length that really is
                    if self._reader.get(
                            self.SHEET, self.HEADER_ROW, col,
                            (basestring, float)) == "End May '18":
                        continue
                    # TODO: extracted unnecessarily many times
                    term = self._reader.get(
                        self.SHEET, self.HEADER_ROW, col, (int, float))

                    price = self._reader.get(self.SHEET, row, col,
                                             (float, basestring, type(None)))
                    # skip blanks
                    if price in (None, ""):
                        continue
                    _assert_true(type(price) is float)

                    for rate_class_id in self.get_rate_class_ids_for_alias(
                            rate_class_alias):
                        quote = MatrixQuote(
                            start_from=start_from, start_until=start_until,
                            term_months=term, valid_from=self._valid_from,
                            valid_until=self._valid_until,
                            min_volume=min_volume, limit_volume=limit_volume,
                            purchase_of_receivables=False,
                            rate_class_alias=rate_class_alias, price=price)
                        quote.rate_class_id = rate_class_id
                        yield quote


class ChampionMatrixParser(QuoteParser):
    """ Parser for Champion Matrix Rates
    """

    FILE_FORMAT = formats.xls

    HEADER_ROW = 13
    VOLUME_RANGE_COL = 'H'
    QUOTE_START_ROW = 14
    QUOTE_END_ROW = 445
    RATE_CLASS_COL = 'F'
    EDC_COL = 'E'
    DESCRIPTION_COL = 'G'
    TERM_START_COL = 'I'
    TERM_END_COL = 'L'
    PRICE_START_COL = 'I'
    PRICE_END_COL = 'K'
    STATE_COL = 'D'
    START_DATE_COL = 'C'

    EXPECTED_SHEET_TITLES = [
        'PA',
        'OH',
        'IL',
        'NJ',
        'MD'
    ]

    DATE_CELL = ('PA', 8, 'C', None)

    def _extract_volume_range(self, sheet,row, col):
        regex = r'(\d+)-(\d+) MWh'
        low, high = self._reader.get_matches(sheet, row, col, regex,
                                             (int, int))
        if low % 10 == 1:
            low -= 1
        return low * 1000, high * 1000

    def _extract_quotes(self):
        for sheet in self.EXPECTED_SHEET_TITLES:

            for row in xrange(self.QUOTE_START_ROW,
                              self._reader.get_height(sheet)):
                state = self._reader.get(sheet, row, self.STATE_COL,
                                         basestring)
                if state == '':
                    continue

                edc = self._reader.get(sheet, row, self.EDC_COL,
                                         basestring)

                description = self._reader.get(sheet, row,self.DESCRIPTION_COL,
                                         basestring)

                rate_class_name = self._reader.get(sheet, row,
                    self.RATE_CLASS_COL, basestring)
                rate_class_alias = '-'.join(
                    [state, edc, rate_class_name, description])

                start_from = excel_number_to_datetime(self._reader.get(
                    sheet, row, self.START_DATE_COL, float))

                start_until = date_to_datetime((Month(start_from) + 1).first)

                min_volume, limit_volume = self._extract_volume_range(sheet,row,
                                                        self.VOLUME_RANGE_COL)

                for col in self._reader.column_range(self.TERM_START_COL,
                                                     self.TERM_END_COL):
                    price = float(self._reader.get(sheet, row, col,
                                                  (float, basestring,
                                                   type(None))))/1000

                    term = self._reader.get_matches(
                                            sheet, self.HEADER_ROW, col,
                                            '(\d+) mths', int)

                    for rate_class_id in self.get_rate_class_ids_for_alias(
                            rate_class_alias):
                        quote = MatrixQuote(start_from=start_from,
                            start_until=start_until, term_months=term,
                            valid_from=self._valid_from,
                            valid_until=self._valid_until,
                            min_volume=min_volume,
                            limit_volume=limit_volume,
                            purchase_of_receivables=False, price=price,
                            rate_class_alias=rate_class_alias)
                        # TODO: rate_class_id should be determined automatically
                        # by setting rate_class
                        if rate_class_id is not None:
                            quote.rate_class_id = rate_class_id
                        yield quote


class AmerigreenMatrixParser(QuoteParser):
    """Parser for Amerigreen spreadsheet.
    """
    # original spreadsheet is in "xlsx" format. but reading it using
    # tablib.formats.xls gives this error from openpyxl:
    # "ValueError: Negative dates (-0.007) are not supported"
    # solution: open in Excel and re-save in "xls" format.
    FILE_FORMAT = formats.xls

    HEADER_ROW = 25
    QUOTE_START_ROW = 26
    UTILITY_COL = 'C'
    STATE_COL = 'D'
    TERM_COL = 'E'
    START_MONTH_COL = 'F'
    START_DAY_COL = 'G'
    PRICE_COL = 'N'

    # Amerigreen builds in the broker fee to the prices, so it must be
    # subtracted from the prices shown
    BROKER_FEE_CELL = (22, 'F')

    EXPECTED_SHEET_TITLES = None
    EXPECTED_CELLS = [
        (0, 11, 'C', 'AMERIgreen Energy Daily Matrix Pricing'),
        (0, 13, 'C', "Today's Date:"),
        (0, 15, 'C', 'The Matrix Rates include a \$0.0200/therm Broker Fee'),
        (0, 15, 'J', 'All rates are quoted at the burner tip and include LDC '
                     'Line Loss fees'),
        (0, 16, 'J', 'Quotes are valid through the end of the business day'),
        (0, 17, 'J',
         'Valid for accounts with annual volume of up to 50,000 therms'),
        (0, 19, 'J',
         "O&R and PECO rates are in Ccf's, all others are in Therms"),
        (0, HEADER_ROW, 'C', 'LDC'),
        (0, HEADER_ROW, 'D', 'State'),
        (0, HEADER_ROW, 'E', 'Term \(Months\)'),
        (0, HEADER_ROW, 'F', 'Start Month'),
        (0, HEADER_ROW, 'G', 'Start Day'),
        (0, HEADER_ROW, 'J', 'Broker Fee'),
        (0, HEADER_ROW, 'K', "Add'l Fee"),
        (0, HEADER_ROW, 'L', "Total Fee"),
        (0, HEADER_ROW, 'M', "Heat"),
        (0, HEADER_ROW, 'N', "Flat"),
    ]
    DATE_FILE_NAME_REGEX = 'Amerigreen Matrix (\d\d-\d\d-\d\d\d\d)\s*\..+'

    def _extract_quotes(self):
        broker_fee = self._reader.get(0, self.BROKER_FEE_CELL[0],
                                      self.BROKER_FEE_CELL[1], float)

        # "Valid for accounts with annual volume of up to 50,000 therms"
        min_volume, limit_volume = 0, 50000

        for row in xrange(self.QUOTE_START_ROW, self._reader.get_height(0)):
            utility = self._reader.get(0, row, self.UTILITY_COL, basestring)
            # detect end of quotes by blank cell in first column
            if utility == "":
                break

            state = self._reader.get(0, row, self.STATE_COL, basestring)
            rate_class_alias = state + '-' + utility

            term_months = self._reader.get(0, row, self.TERM_COL, (int, float))

            start_from = excel_number_to_datetime(
                self._reader.get(0, row, self.START_MONTH_COL, float))
            start_day_str = self._reader.get(0, row, self.START_DAY_COL,
                                             basestring)
            _assert_true(start_day_str in ('1st of the Month',
                                           'On Cycle Read Date'))
            # TODO: does "1st of the month" really mean starting only on one day?
            start_until = start_from + timedelta(days=1)

            price = self._reader.get(0, row, self.PRICE_COL, float) - broker_fee

            for rate_class_id in self.get_rate_class_ids_for_alias(
                    rate_class_alias):
                quote = MatrixQuote(
                    start_from=start_from, start_until=start_until,
                    term_months=term_months, valid_from=self._valid_from,
                    valid_until=self._valid_until,
                    min_volume=min_volume, limit_volume=limit_volume,
                    rate_class_alias=rate_class_alias,
                    purchase_of_receivables=False, price=price)
                # TODO: rate_class_id should be determined automatically
                # by setting rate_class
                if rate_class_id is not None:
                    quote.rate_class_id = rate_class_id
                yield quote

