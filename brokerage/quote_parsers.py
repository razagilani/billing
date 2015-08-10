"""Code for reading quote files. Could include both matrix quotes and custom
quotes.
"""
from abc import ABCMeta, abstractmethod
from itertools import chain, izip
import re
from datetime import datetime, timedelta, date

from tablib import Databook, formats
from core.model import AltitudeSession

from exc import ValidationError, BillingError
from util.dateutils import parse_date, parse_datetime, date_to_datetime, \
    excel_number_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote, load_rate_class_aliases


# TODO:
# - time zones are ignored but are needed because quote validity times,
# start dates, are specific to customers in a specific time zone
# - extract duplicate code for volume ranges across subclasses


def _assert_true(p):
    if not p:
        raise ValidationError('Assertion failed')


def _assert_equal(a, b):
    if a != b:
        raise ValidationError("Expected %s, found %s" % (a, b))


def _assert_match(regex, string):
    if not re.match(regex, string):
        raise ValidationError('No match for "%s" in "%s"' % (regex, string))


def parse_number(string):
    """Convert number string into a number.
    :param string: number string formatted for American humans (with commas)
    :return: int (if the number is really an integer) or float
    """
    result = float(string.replace(',', ''))
    if result == round(result):
        return int(result)
    return result


def excel_number_to_datetime(number):
    """Dates in some XLS spreadsheets will appear as numbers of days since
    (apparently) December 30, 1899.
    :param number: int or float
    :return: datetime
    """
    return datetime(1899, 12, 30) + timedelta(days=number)


class SpreadsheetReader(object):
    """Wrapper for tablib.Databook with methods to easily get data from
    spreadsheets.
    """
    LETTERS = ''.join(chr(ord('A') + i) for i in xrange(26))

    @classmethod
    def column_range(cls, start, stop, step=1):
        """Return a list of column numbers numbers between the given column
        numbers or letters (like the built-in "range" function, but allows
        letters).
        :param start: inclusive start column letter or number (required
        unlike in the "range" function)
        :param end: exclusive end column letter or number
        :param step: int
        """
        if isinstance(start, basestring):
            start = cls._col_letter_to_index(start)
        if isinstance(stop, basestring):
            limit = cls._col_letter_to_index(stop)
        return range(start, limit, step)

    @classmethod
    def _col_letter_to_index(cls, letter):
        """
        :param letter: A-Z (string)
        :return index of spreadsheet column.
        """
        letter = letter.upper()
        try:
            return cls.LETTERS.index(letter)
        except ValueError:
            raise ValueError('Invalid column letter "%s"' % letter)

    @classmethod
    def _row_number_to_index(cls, number):
        """
        :param number: number as shown in Excel
        :return: tablib row number (where -1 means the "header")
        """
        if number < 0:
            raise ValueError('Negative row number')
        return number - 2

    @classmethod
    def get_databook_from_file(cls, quote_file, file_format):
        """
        :param quote_file: file object
        :return: tablib.Databook
        """
        # tablib's "xls" format takes the file contents as a string as its
        # argument, but "xlsx" and others take a file object
        result = Databook()
        if file_format in [formats.xlsx]:
            file_format.import_book(result, quote_file)
        elif file_format in [formats.xls]:
            file_format.import_book(result, quote_file.read())
        else:
            raise BillingError('Unknown format: %s' % format.__name__)
        return result

    def __init__(self):
        # Databook representing whole spreadsheet and relevant sheet
        # respectively
        self._databook = None

    def _get_sheet(self, sheet_number_or_title):
        """
        :param sheet_number_or_title: 0-based index (int) or title (string)
        of the sheet to use
        """
        if isinstance(sheet_number_or_title, int):
            return self._databook.sheets()[0]
        assert isinstance(sheet_number_or_title, basestring)
        try:
            return next(s for s in self._databook.sheets() if
                        s.title == sheet_number_or_title)
        except StopIteration:
            raise ValueError('No sheet named "%s"' % sheet_number_or_title)

    def load_file(self, quote_file, file_format):
        """Read from 'quote_file'. May be very slow and take a huge amount of
        memory.
        :param quote_file: file to read from.
        """
        self._databook = self.get_databook_from_file(quote_file, file_format)

    def is_loaded(self):
        """:return: True if file has been loaded, False otherwise.
        """
        return self._databook is not None

    def get_sheet_titles(self):
        """:return: list of titles of all sheets (strings)
        """
        return [s.title for s in self._databook.sheets()]

    def get_height(self, sheet_number_or_title):
        """Return the number of rows in the given sheet.
        :param sheet_number_or_title: 0-based index (int) or title (string)
        of the sheet to use
        :return: int
        """
        # tablib does not count the "header" as a row
        return self._get_sheet(sheet_number_or_title).height + 1

    def get(self, sheet_number_or_title, row, col, the_type):
        """Return a value extracted from the cell of the given sheet at (row,
        col), and expect the given type (e.g. int, float, basestring, datetime).
        Raise ValidationError if the cell does not exist or has the wrong type.
        :param sheet_number_or_title: 0-based index (int) or title (string)
        of the sheet to use
        :param row: Excel-style row number (int)
        :param col: column index (int) or letter (string)
        :param the_type: expected type of the cell contents
        """
        sheet = self._get_sheet(sheet_number_or_title)
        y = self._row_number_to_index(row)
        x = col if isinstance(col, int) else self._col_letter_to_index(col)
        try:
            if y == -1:
                # 1st row is the header, 2nd row is index "0"
                value = sheet.headers[x]
            else:
                value = sheet[y][x]
        except IndexError:
            raise ValidationError('No cell (%s, %s)' % (row, col))
        if not isinstance(value, the_type):
            raise ValidationError(
                'At (%s,%s), expected type %s, found "%s" with type %s' % (
                    row, col, the_type, value, type(value)))
        return value

    def get_matches(self, sheet_number_or_title, row, col, regex, types):
        """Get list of values extracted from the spreadsheet cell at
        (row, col) using groups (parentheses) in a regular expression. Values
        are converted from strings to the given types. Raise ValidationError
        if there are 0 matches or the wrong number of matches or any value
        could not be converted to the expected type.
        :param sheet_number_or_title: 0-based index (int) or title (string)
        of the sheet to use
        :param row: row index (int)
        :param col: column index (int) or letter (string)
        :param regex: regular expression string
        :param types: expected type of each match represented as a callable
        that converts a string to that type, or a list/tuple of them whose
        length corresponds to the number of matches.
        :return: resulting value or list of values
        Example:
        >>> self.get_matches(1, 2, '(\d+/\d+/\d+)', parse_date)
        >>> self.get_matches(3, 4, r'(\d+) ([A-Za-z])', (int, str))
        """
        if not isinstance(types, (list, tuple)):
            types = [types]
        text = self.get(sheet_number_or_title, row, col, basestring)
        _assert_match(regex, text)
        m = re.match(regex, text)
        if len(m.groups()) != len(types):
            raise ValidationError
        results = []
        for group, the_type in zip(m.groups(), types):
            try:
                value = the_type(group)
            except ValueError:
                raise ValidationError
            results.append(value)
        if len(results) == 1:
            return results[0]
        return results


class QuoteParser(object):
    """Superclass for classes representing particular spreadsheet formats.
    These should contain everything format-specific, but not general-purpose
    code for reading spreadsheets.
    """
    __metaclass__ = ABCMeta

    # tablib submodule that should be used to import data from the spreadsheet
    FILE_FORMAT = None

    # subclasses can set this to use sheet titles to validate the file
    EXPECTED_SHEET_TITLES = None

    # subclassses can fill this with (row, col, regex) tuples to assert
    # expected contents of certain cells
    EXPECTED_CELLS = []

    # optional (row, col, regex) for for the validity/expiration date of every
    # quote in this matrix: regex must have 1 parenthesized group that can be
    # parsed as a date
    DATE_CELL = None

    def __init__(self):
        self._reader = SpreadsheetReader()

        # whether validation has been done yet
        self._validated = False

        # optional validity date and expiration date of all quotes (matrix
        # quote spreadsheets tend have a date on them and are good for one day)
        self._date = None

        # number of quotes read so far
        self._count = 0

        # mapping of rate class alias to rate class ID, loaded in advance to
        # avoid repeated queries
        self._rate_class_aliases = load_rate_class_aliases()

    def load_file(self, quote_file):
        """Read from 'quote_file'. May be very slow and take a huge amount of
        memory.
        :param quote_file: file to read from.
        """
        self._reader.load_file(quote_file, self.FILE_FORMAT)
        self._validated = False

    def validate(self):
        """Raise ValidationError if the file does not match expectations about
        its format. This is supposed to detect format changes or prevent
        reading the wrong file by accident, not to find all possible
        problems the contents in advance.
        """
        assert self._reader.is_loaded()
        if self.EXPECTED_SHEET_TITLES is not None:
            _assert_true(set(self.EXPECTED_SHEET_TITLES).issubset(
                    set(self._reader.get_sheet_titles())))
        for sheet_number_or_title, row, col, regex in self.EXPECTED_CELLS:
            text = self._reader.get(sheet_number_or_title, row, col, basestring)
            _assert_match(regex, text)
        self._validate()
        self._validated = True

    def _validate(self):
        # subclasses can override this to do additional validation
        pass

    def get_rate_class_ids_for_alias(self, alias):
        """Return ID of rate class for the given alias, if there is one,
        otherwise None.
        """
        try:
            rate_class_ids = self._rate_class_aliases[alias]
        except KeyError:
            return [None]
        return rate_class_ids

    def extract_quotes(self):
        """Yield Quotes extracted from the file. Raise ValidationError if the
        quote file is malformed (no other exceptions should not be raised).
        The Quotes are not associated with a supplier, so this must be done
        by the caller.
        """
        if not self._validated:
            self.validate()

        # extract the date using DATE_CELL
        sheet_number_or_title, row, col, regex = self.DATE_CELL
        if regex is None:
            cell_value = self._reader.get(sheet_number_or_title, row, col,
                                          (datetime, int, float))
            if isinstance(cell_value, (int, float)):
                cell_value = excel_number_to_datetime(cell_value)
            self._date = cell_value
        else:
            print sheet_number_or_title, row, col, regex
            self._date = self._reader.get_matches(sheet_number_or_title, row,
                                                  col, regex, parse_datetime)
        for quote in self._extract_quotes():
            self._count += 1
            yield quote

    @abstractmethod
    def _extract_quotes(self):
        """Subclasses do extraction here. Should be implemented as a generator
        so consumers can control how many quotes get read at one time.
        """
        raise NotImplementedError

    def get_count(self):
        """
        :return: number of quotes read so far
        """
        return self._count


class DirectEnergyMatrixParser(QuoteParser):
    """Parser for Direct Energy spreadsheet.
    """
    FILE_FORMAT = formats.xls

    HEADER_ROW = 51
    VOLUME_RANGE_ROW = 51
    QUOTE_START_ROW = 52
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

    def _extract_volume_range(self, row, col):
        # these cells are strings like like "75-149" where "149" really
        # means < 150, so 1 is added to the 2nd number--unless it is the
        # highest volume range, in which case the 2nd number really means
        # what it says.
        regex = r'(\d+)\s*-\s*(\d+)'
        low, high = self._reader.get_matches(0, row, col, regex, (float, float))
        if col != self.PRICE_END_COL:
            high += 1
        return low * 1000, high * 1000

    def _extract_quotes(self):
        volume_ranges = [self._extract_volume_range(self.VOLUME_RANGE_ROW, col)
                         for col in xrange(self.PRICE_START_COL,
                                           self.PRICE_END_COL + 1)]
        # volume ranges should be contiguous
        for i, vr in enumerate(volume_ranges[:-1]):
            next_vr = volume_ranges[i + 1]
            _assert_equal(vr[1], next_vr[0])

        for row in xrange(self.QUOTE_START_ROW, self._reader.get_height(0)):
            # TODO use time zone here
            start_from = excel_number_to_datetime(
                self._reader.get(0, row, 0, (int, float)))
            start_until = date_to_datetime((Month(start_from) + 1).first)
            term_months = self._reader.get(0, row, self.TERM_COL, (int, float))

            # rate class names are separated by commas and optional whitespace
            rate_class_text = self._reader.get(0, row, self.RATE_CLASS_COL,
                                               basestring)
            rate_class_aliases = [s.strip() for s in rate_class_text.split(',')]

            special_options = self._reader.get(0, row, self.SPECIAL_OPTIONS_COL,
                                               basestring)
            _assert_true(special_options in ['', 'POR', 'UCB', 'RR'])

            for col in xrange(self.PRICE_START_COL, self.PRICE_END_COL + 1):
                min_vol, max_vol = volume_ranges[col - self.PRICE_START_COL]
                price = self._reader.get(0, row, col, (int, float)) / 1000.
                for alias in rate_class_aliases:
                    for rate_class_id in self.get_rate_class_ids_for_alias(
                            alias):
                        quote = MatrixQuote(
                            start_from=start_from, start_until=start_until,
                            term_months=term_months, valid_from=self._date,
                            valid_until=self._date + timedelta(days=1),
                            min_volume=min_vol, limit_volume=max_vol,
                            rate_class_alias=alias,
                            purchase_of_receivables=(special_options == 'POR'),
                            price=price)
                        # TODO: rate_class_id should be determined automatically
                        # by setting rate_class
                        if rate_class_id is not None:
                            quote.rate_class_id = rate_class_id
                        yield quote


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

                rate_class_alias = self._reader.get(sheet, row, 2,
                                                    (basestring, type(None)))
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
                                term_months=term, valid_from=self._date,
                                valid_until=self._date + timedelta(days=1),
                                min_volume=min_volume, limit_volume=limit_volume,
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
            rate_class = self._reader.get(self.SHEET, row,
                                              self.RATE_CLASS_COL, basestring)

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
                            rate_class):
                        quote = MatrixQuote(
                            start_from=start_from, start_until=start_until,
                            term_months=term, valid_from=self._date,
                            valid_until=self._date + timedelta(days=1),
                            min_volume=min_volume, limit_volume=limit_volume,
                            purchase_of_receivables=False,
                            rate_class_alias=rate_class, price=price)
                        quote.rate_class_id = rate_class_id
                        yield quote


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

                rate_class_alias = self._reader.get(sheet, row, 2,
                                                    (basestring, type(None)))
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
                                term_months=term, valid_from=self._date,
                                valid_until=self._date + timedelta(days=1),
                                min_volume=min_volume, limit_volume=limit_volume,
                                purchase_of_receivables=False, price=price,
                                rate_class_alias=rate_class_alias)
                            # TODO: rate_class_id should be determined automatically
                            # by setting rate_class
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
    RATE_CLASS_COL = 'C'
    STATE_COL = 'D'
    TERM_COL = 'E'
    START_MONTH_COL = 'F'
    START_DAY_COL = 'G'
    PRICE_COL = 'N'

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
    DATE_CELL = (0, 13, 'D', None)

    def _extract_volume_range(self, row, col):
        # these cells are strings like like "75-149" where "149" really
        # means < 150, so 1 is added to the 2nd number--unless it is the
        # highest volume range, in which case the 2nd number really means
        # what it says.
        regex = r'(\d+)\s*-\s*(\d+)'
        low, high = self._reader.get_matches(0, row, col, regex, (float, float))
        if col != self.PRICE_END_COL:
            high += 1
        return low * 1000, high * 1000

    def _extract_quotes(self):
        # "Valid for accounts with annual volume of up to 50,000 therms"
        min_volume, limit_volume = 0, 50000
        print self._date

        for row in xrange(self.QUOTE_START_ROW, self._reader.get_height(0)):
            rate_class_alias = self._reader.get(0, row, self.RATE_CLASS_COL,
                                                basestring)
            # detect end of quotes by blank cell in first column
            if rate_class_alias == "":
                break

            # TODO: state may not be used
            state = self._reader.get(0, row, self.STATE_COL, basestring)

            term_months = self._reader.get(0, row, self.TERM_COL, (int, float))

            start_from = excel_number_to_datetime(
                self._reader.get(0, row, self.START_MONTH_COL, float))
            start_day_str = self._reader.get(0, row, self.START_DAY_COL,
                                             basestring)
            _assert_true(start_day_str in ('1st of the Month',
                                           'On Cycle Read Date'))
            # TODO: does "1st of the month" really mean starting only on one day?
            start_until = start_from + timedelta(days=1)

            price = self._reader.get(0, row, self.PRICE_COL, float)

            for rate_class_id in self.get_rate_class_ids_for_alias(
                    rate_class_alias):
                quote = MatrixQuote(
                    start_from=start_from, start_until=start_until,
                    term_months=term_months, valid_from=self._date,
                    valid_until=self._date + timedelta(days=1),
                    min_volume=min_volume, limit_volume=limit_volume,
                    rate_class_alias=rate_class_alias,
                    purchase_of_receivables=False, price=price)
                # TODO: rate_class_id should be determined automatically
                # by setting rate_class
                if rate_class_id is not None:
                    quote.rate_class_id = rate_class_id
                yield quote

