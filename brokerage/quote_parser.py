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
from util.units import unit_registry


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
    def column_range(cls, start, stop, step=1, inclusive=True):
        """Return a list of column numbers numbers between the given column
        numbers or letters (like the built-in "range" function, but inclusive
        by default and allows letters).
        :param start: inclusive start column letter or number (required
        unlike in the "range" function)
        :param stop: inclusive end column letter or number
        :param step: int
        :param inclusive: if False, 'stop' column is not included
        """
        if isinstance(start, basestring):
            start = cls._col_letter_to_index(start)
        if isinstance(stop, basestring):
            stop = cls._col_letter_to_index(stop)
        if inclusive:
            stop += 1
        return range(start, stop, step)

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

    def get_width(self, sheet_number_or_title):
        """Return the number of columns in the given sheet.
        :param sheet_number_or_title: 0-based index (int) or title (string)
        of the sheet to use
        :return: int
        """
        return self._get_sheet(sheet_number_or_title).width

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
                'neighbors are %s' % (
                row, col, the_type, value, type(value), get_neighbor_str()))
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


class DateGetter(object):
    """Handles determining the validity dates for quotes in QuoteParser.
    """
    __metaclass__ = ABCMeta

    def get_dates(self, quote_parser):
        """
        :return: tuple of 2 datetimes: quote validity start (inclusive) and
        end (exclusive)
        """
        raise NotImplementedError

class SimpleCellDateGetter(DateGetter):
    """Gets the date from a cell on the spreadsheet. There is only one date:
    quotes are assumed to expire 1 day after they become valid.
    """
    def __init__(self, sheet, row, col, regex):
        """
        :param sheet: sheet name or index
        :param row: row number
        :param col: column letter or index
        :param regex: regular expression string with 1 parenthesized group
        that can be parsed as a date, or None if the cell value is expected
        to be a date already.
        """
        self._sheet = sheet
        self._row = row
        self._col = col
        self._regex = regex

    def _get_date_from_cell(self, spreadsheet_reader, row, col):
        if self._regex is None:
            value = spreadsheet_reader.get(self._sheet, row, col,
                                           (datetime, int, float))
            if isinstance(value, (int, float)):
                value = excel_number_to_datetime(value)
            return value
        return spreadsheet_reader.get_matches(self._sheet, self._row, self._col,
                                              self._regex, parse_datetime)

    def get_dates(self, quote_parser):
        # TODO: use of private variable
        valid_from = self._get_date_from_cell(quote_parser._reader, self._row,
                                              self._col)
        valid_until = valid_from + timedelta(days=1)
        return valid_from, valid_until


class StartEndCellDateGetter(SimpleCellDateGetter):
    """Gets the start date and separate end date from two different cells.
    """
    def __init__(self, sheet, start_row, start_col, end_row, end_col, regex):
        """
        :param sheet: sheet name or index for both dates
        :param start_row: start date row number
        :param start_col: start date column letter or index
        :param end_row: end date row number
        :param end_col: end date column letter or index
        :param regex: regular expression string with 1 parenthesized group
        that can be parsed as a date, or None if the cell value is expected
        to be a date already. applies to both dates.
        """
        super(StartEndCellDateGetter, self).__init__(
            sheet, start_row, start_col, regex)
        self._end_row = end_row
        self._end_col = end_col

    def get_dates(self, quote_parser):
        valid_from, _ = super(StartEndCellDateGetter, self).get_dates(
            quote_parser)
        # TODO: use of private variable
        valid_until = self._get_date_from_cell(quote_parser._reader,
                                               self._end_row, self._end_col)
        return valid_from, valid_until + timedelta(days=1)


class FileNameDateGetter(DateGetter):
    """Gets the date from the file name."""
    def __init__(self, regex):
        """
        :param regex: must match the file name and have 1 parenthesized group
        that can be parsed as a date.
        """
        self._regex = regex

    def get_dates(self, quote_parser):
        match = re.match(self._regex, quote_parser.file_name)
        if match == None:
            raise ValidationError('No match for "%s" in file name "%s"' % (
                self._regex, quote_parser.file_name))
        valid_from = parse_datetime(match.group(1))
        return valid_from, valid_from + timedelta(days=1)


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

    # energy unit that the supplier uses: convert from this. subclass should
    # specify it.
    EXPECTED_ENERGY_UNIT = None

    # energy unit for resulting quotes: convert to this
    TARGET_ENERGY_UNIT = unit_registry.kWh

    # a DateGetter instance that determines the validity/expiration dates of
    # all quotes. not required, because some some suppliers could have
    # different dates for some quotes than for others.
    date_getter = None

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
        self._validated = False
        self.file_name = file_name

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

    def extract_quotes(self):
        """Yield Quotes extracted from the file. Raise ValidationError if the
        quote file is malformed (no other exceptions should not be raised).
        The Quotes are not associated with a supplier, so this must be done
        by the caller.
        """
        if not self._validated:
            self.validate()

        if self.date_getter is not None:
            self._valid_from, self._valid_until = self.date_getter.get_dates(self)

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

    def _extract_volume_range(self, sheet, row, col, regex, fudge_low=False,
                              fudge_high=False, fudge_block_size=10):
        """
        Extract numbers representing a range of energy consumption from a
        spreadsheet cell with a string in it like "150-200 MWh" or
        "Below 50,000 ccf/therms".
        :param sheet_number_or_title: 0-based index (int) or title (string)
        of the sheet to use
        :param row: row index (int)
        :param col: column index (int) or letter (string)
        :param regex: regular expression string or re.RegexObject containing
        either or both of two named groups, "low" and "high". (Notation is
        "(?P<name>...)": see
        https://docs.python.org/2/library/re.html#regular-expression-syntax)
        :param expected_unit: pint.unit.Quantity representing the unit used
        in the spreadsheet (such as util.units.unit_registry.MWh)
        :param target_unit: pint.unit.Quantity representing the unit to be
        used in the return value (such as util.units.unit_registry.kWh)
        :param fudge_low: if True, and the low value of the range is 1 away
        from a multiple of 'fudge_block_size', adjust it to the nearest
        multiple of 'fudge_block_size'.
        :param fudge_high: if True, and the high value of the range is 1 away
        from a multiple of 'fudge_block_size', adjust it to the nearest
        multiple of 'fudge_block_size'.
        :param fudge_block_size: int (10 usually works; 100 would provide
        extra validation; sometimes 5 is needed)
        :return: low value (int), high value (int)
        """
        # TODO: probably should allow callers to specify whether the fudging
        # should be positive only or negative only (it's never both). this
        # will help prevent errors.
        if isinstance(regex, basestring):
            regex = re.compile(regex)
        assert regex.groupindex in ({'low': 1, 'high': 2},
                                    {'low': 2, 'high': 1})
        values = self._reader.get_matches(sheet, row, col, regex,
                                          (int,) * regex.groups)
        if regex.groupindex['low'] == 1:
            low, high = values
        else:
            high, low = values
        if fudge_low:
            if low % fudge_block_size == 1:
                low -= 1
            elif low % fudge_block_size == fudge_block_size - 1:
                low += 1
        if fudge_high:
            if high % fudge_block_size == 1:
                high -= 1
            elif high % fudge_block_size == fudge_block_size - 1:
                high += 1
        low = int(low * self.EXPECTED_ENERGY_UNIT.to(
            self.TARGET_ENERGY_UNIT) / self.TARGET_ENERGY_UNIT)
        high = int(high * self.EXPECTED_ENERGY_UNIT.to(
            self.TARGET_ENERGY_UNIT) / self.TARGET_ENERGY_UNIT)
        return low, high

    def _extract_volume_ranges_horizontal(
            self, sheet, row, start_col, end_col, regex,
            allow_restarting_at_0=False, **kwargs):
        """Extract a set of energy consumption ranges along a row, and also
        check that the ranges are contiguous.
        :param allow_restarting_at_0: if True, going from a big number back
        to 0 doesn't violate contiguity.
        See _extract_volume_range for other arguments.
        """
        # TODO: too many arguments. use of **kwargs makes code hard to follow.
        # some of these arguments could be instance variables instead.
        result = [
            self._extract_volume_range(sheet, row, col, regex, **kwargs)
            for col in self._reader.column_range(start_col, end_col)]

        # volume ranges should be contiguous or restarting at 0
        for i, vr in enumerate(result[:-1]):
            next_vr = result[i + 1]
            if not allow_restarting_at_0 or next_vr[0] != 0:
                _assert_equal(vr[1], next_vr[0])

        return result