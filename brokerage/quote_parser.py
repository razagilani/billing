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

    def _get_cell(self, sheet, x, y):
        if y == -1:
            # 1st row is the header, 2nd row is index "0"
            return sheet.headers[x]
        return sheet[y][x]

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
            value = self._get_cell(sheet, x, y)
        except IndexError:
            raise ValidationError('No cell (%s, %s)' % (row, col))

        def get_neighbor_str():
            result = ''
            # clockwise: left up right down
            for dir, nx, ny in [('up', x, y - 1), ('down', x, y + 1),
                                ('left', x - 1, y), ('right', x + 1, y)]:
                try:
                    nvalue = self._get_cell(sheet, nx, ny)
                except IndexError as e:
                    nvalue = repr(e)
                result += '%s: %s ' % (dir, nvalue)
            return result

        if not isinstance(value, the_type):
            raise ValidationError(
                'At (%s,%s), expected type %s, found "%s" with type %s. '
                'neighbors are %s' % (row, col, the_type, value, type(value),
                                      get_neighbor_str()))
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

    # two ways to get the validity/expiration date of every quote in this
    # matrix. both can't be used in the same QuoteParser class, so at least
    # one must be None.
    # DATE_CELL is an optional (row, col, regex) tuple; regex can be None if
    # the cell value is already a datetime.
    # DATE_FILE_NAME_REGEX is used to extract the date from the file name.
    # in both cases the regex must have 1 parenthesized group that can be
    # parsed as a date.
    DATE_CELL = None
    DATE_FILE_NAME_REGEX = None

    def __init__(self):
        self._reader = SpreadsheetReader()

        # whether validation has been done yet
        self._validated = False

        # optional validity date and expiration dates for all quotes (matrix
        # quote spreadsheets tend have a date on them and are good for one
        # day; some are valid for a longer period of time)
        self._valid_from = None
        self._valid_until = None

        # number of quotes read so far
        self._count = 0

        # mapping of rate class alias to rate class ID, loaded in advance to
        # avoid repeated queries
        self._rate_class_aliases = load_rate_class_aliases()

    def load_file(self, quote_file, file_name=None):
        """Read from 'quote_file'. May be very slow and take a huge amount of
        memory.
        :param quote_file: file to read from.
        :param file_name: name of the file, used in some formats to get
        valid_from and valid_until dates for the quotes
        """
        self._reader.load_file(quote_file, self.FILE_FORMAT)
        self._file_name = file_name
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
        otherwise [None].
        """
        try:
            rate_class_ids = self._rate_class_aliases[alias]
        except KeyError:
            return [None]
        return rate_class_ids

    def _get_dates(self):
        """Return the validity/expiration date for all quotes in the file
        using DATE_CELL or DATE_FILE_NAME_REGEX.
        """
        assert None in (self.DATE_CELL, self.DATE_FILE_NAME_REGEX)

        if self.DATE_CELL is not None:
            sheet_number_or_title, row, col, regex = self.DATE_CELL
            if regex is None:
                valid_from = self._reader.get(sheet_number_or_title, row, col,
                                              (datetime, int, float))
                if isinstance(valid_from, (int, float)):
                    valid_from = excel_number_to_datetime(valid_from)
                return valid_from, valid_from + timedelta(days=1)
            valid_from = self._reader.get_matches(sheet_number_or_title, row,
                                                  col, regex, parse_datetime)
            return valid_from, valid_from + timedelta(days=1)

        if self.DATE_FILE_NAME_REGEX is not None:
            assert isinstance(self._file_name, basestring)
            match = re.match(self.DATE_FILE_NAME_REGEX, self._file_name)
            if match == None:
                raise ValidationError('No match for "%s" in file name "%s"' % (
                    self.DATE_FILE_NAME_REGEX, self._file_name))
            valid_from = parse_datetime(match.group(1))
            return valid_from, valid_from + timedelta(days=1)

        return None

    def extract_quotes(self):
        """Yield Quotes extracted from the file. Raise ValidationError if the
        quote file is malformed (no other exceptions should not be raised).
        The Quotes are not associated with a supplier, so this must be done
        by the caller.
        """
        if not self._validated:
            self.validate()

        self._valid_from, self._valid_until = self._get_dates()

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
                _assert_equal(self._date,
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
                        term_months=term_months, valid_from=self._date,
                        valid_until=self._date + timedelta(days=1),
                        min_volume=min_vol, limit_volume=max_vol,
                        rate_class_alias=rate_class_alias,
                        purchase_of_receivables=False, price=price)
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote
