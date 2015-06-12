"""Code for reading quote files. Could include both matrix quotes and custom
quotes.
"""
from abc import ABCMeta, abstractmethod
import calendar
import re
from datetime import datetime, timedelta, date

from tablib import Databook, formats

from exc import ValidationError, BillingError
from util.dateutils import parse_date, parse_datetime, get_end_of_day, \
    date_to_datetime
from brokerage.brokerage_model import MatrixQuote


# TODO:
# - time zones are ignored but are needed because quote validity times,
# start dates, are specific to customers in a specific time zone
from util.monthmath import Month


def _assert_true(p):
    if not p:
        raise ValidationError('Assertion failed')


def _assert_equal(a, b):
    if a != b:
        raise ValidationError("Expected %s, found %s" % (a, b))


def _assert_match(regex, string):
    if not re.match(regex, string):
        raise ValidationError('No match for "%s" in "%s"' % (regex, string))


def excel_number_to_date(number):
    """Dates in some XLS spreadsheets will appear as numbers of days since
    (apparently) December 30, 1899.
    :param number: int or float
    :return: date
    """
    return date(1899, 12, 30) + timedelta(days=number)


def excel_number_to_datetime(number):
    """Dates in some XLS spreadsheets will appear as numbers of days since
    (apparently) December 30, 1899.
    :param number: int or float
    :return: datetime
    """
    return datetime(1899, 12, 30) + timedelta(days=number)


class QuoteParser(object):
    """Class for parsing a particular quote spreadsheet. This is stateful and
    one instance should be used per file.
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

    @classmethod
    def _get_databook_from_file(cls, quote_file):
        """
        :param quote_file: file object
        :return: tablib.Databook
        """
        # tablib's "xls" format takes the file contents as a string as its
        # argument, but "xlsx" and others take a file object
        result = Databook()
        if cls.FILE_FORMAT in [formats.xlsx]:
            cls.FILE_FORMAT.import_book(result, quote_file)
        elif cls.FILE_FORMAT in [formats.xls]:
            cls.FILE_FORMAT.import_book(result, quote_file.read())
        else:
            raise BillingError('Unknown format: %s' % format.__name__)
        return result

    def __init__(self):
        # Databook and Dataset representing whole spreadsheet and relevant
        # sheet respectively
        self._databook = None
        self._sheet = None

        # whether validation has been done yet
        self._validated = False

        # optional validity date and expiration date of all quotes (matrix
        # quote spreadsheets tend have a date on them and are good for one day)
        self._date = None

    def load_file(self, quote_file):
        """Read from 'quote_file'. May be very slow and take a huge amount of
        memory.
        :param quote_file: file to read from.
        """
        self._databook = self._get_databook_from_file(quote_file)
        # it is assumed that only one sheet actually contains the quotes
        self._sheet = self._databook.sheets()[0]
        self._validated = False

    def validate(self):
        """Raise ValidationError if the file does not match expectations about
        its format. This is supposed to detect format changes or prevent
        reading the wrong file by accident, not to find all possible
        problems the contents in advance.
        """
        assert self._databook is not None
        if self.EXPECTED_SHEET_TITLES is not None:
            _assert_equal(self.EXPECTED_SHEET_TITLES,
                          [s.title for s in self._databook.sheets()])
        for row, col, regex in self.EXPECTED_CELLS:
            text = self._get(row, col, basestring)
            _assert_match(regex, text)
        self._validate()
        self._validated = True

    def _validate(self):
        # subclasses can override this to do additional validation
        pass

    def extract_quotes(self):
        """Yield Quotes extracted from the file. Raise ValidationError if the
        quote file is malformed (no other exceptions should not be raised).
        """
        if not self._validated:
            self.validate()

        # extract the date using DATE_CELL
        row, col, regex = self.DATE_CELL
        self._date = self._get_matches(row, col, regex, parse_datetime)

        return self._extract_quotes()

    @abstractmethod
    def _extract_quotes(self):
        # subclasses do extraction here
        raise NotImplementedError

    def _get(self, row, col, the_type):
        """Return a value extracted from the spreadsheet cell at (row, col),
        and expect the given type (e.g. int, float, basestring, datetime).
        Raise ValidationError if the cell does not exist or has the wrong type.
        :param row: row index
        :param row: column index
        :param the_type: expected type of the cell contents
        """
        try:
            if row == -1:
                # 1st row is the header, 2nd row is index "0"
                value = self._sheet.headers[col]
            else:
                value = self._sheet[row][col]
        except IndexError:
            raise ValidationError('No cell (%s, %s)' % (row, col))
        if not isinstance(value, the_type):
            raise ValidationError(
                'Expected type %s, found "%s" with type %s' % (
                    the_type, value, type(value)))
        return value

    def _get_matches(self, row, col, regex, types):
        """Get list of values extracted from the spreadsheet cell at
        (row, col) using groups (parentheses) in a regular expression. Values
        are converted from strings to the given types. Raise ValidationError
        if there are 0 matches or the wrong number of matches or any value
        could not be converted to the expected type.
        :param row: row index
        :param col: column index
        :param regex: regular expression string
        :param types: expected type of each match represented as a callable
        that converts a string to that type, or a list/tuple of them whose
        length corresponds to the number of matches.
        :return: resulting value or list of values
        Example:
        >>> self._get_matches(1, 2, '(\d+/\d+/\d+)', parse_date)
        >>> self._get_matches(3, 4, r'(\d+) ([A-Za-z])', (int, str))
        """
        if not isinstance(types, (list, tuple)):
            types = [types]
        text = self._get(row, col, basestring)
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


class DirectEnergyMatrixParser(QuoteParser):
    """Parser for Direct Energy spreadsheet.
    """
    FILE_FORMAT = formats.xls

    HEADER_ROW = 49
    VOLUME_RANGE_ROW = 49
    QUOTE_START_ROW = 50
    TERM_COL = 7
    PRICE_START_COL = 8
    PRICE_END_COL = 13

    EXPECTED_SHEET_TITLES = [
        'Daily Matrix Price',
    ]
    EXPECTED_CELLS = [
        (-1, 0, 'Direct Energy HQ - Daily Matrix Price Report'),
        (HEADER_ROW, 0, 'Contract Start Month'),
        (HEADER_ROW, 1, 'State'),
        (HEADER_ROW, 2, 'Utility'),
        (HEADER_ROW, 3, 'Zone'),
        (HEADER_ROW, 4, r'Rate Code\(s\)'),
        (HEADER_ROW, 5, 'Product Special Options'),
        (HEADER_ROW, 6, 'Billing Method'),
        (HEADER_ROW, 7, 'Term'),
    ]
    DATE_CELL = (1, 0, 'as of (\d+/\d+/\d+)')

    def _extract_volume_range(self, row, col):
        # these cells are strings like like "75-149" where "149" really
        # means < 150, so 1 is added to the 2nd number--unless it is the
        # highest volume range, in which case the 2nd number really means
        # what it says.
        regex = r'(\d+)\s*-\s*(\d+)'
        low, high = self._get_matches(row, col, regex, (float, float))
        if col != self.PRICE_END_COL:
            high += 1
        return low, high

    def _extract_quotes(self):
        volume_ranges = [self._extract_volume_range(self.VOLUME_RANGE_ROW, col)
                         for col in xrange(self.PRICE_START_COL,
                                           self.PRICE_END_COL + 1)]
        # volume ranges should be contiguous
        for i, vr in enumerate(volume_ranges[:-1]):
            next_vr = volume_ranges[i + 1]
            _assert_equal(vr[1], next_vr[0])

        for row in xrange(self.QUOTE_START_ROW, self._sheet.height):
            # TODO use time zone here
            start_from = excel_number_to_datetime(
                self._get(row, 0, (int, float)))
            start_until = date_to_datetime((Month(start_from) + 1).first)
            term_months = self._get(row, self.TERM_COL, (int, float))

            for col in xrange(self.PRICE_START_COL, self.PRICE_END_COL + 1):
                min_vol, max_vol = volume_ranges[col - self.PRICE_START_COL]
                price = self._get(row, col, (int, float)) / 100.
                yield MatrixQuote(
                    start_from=start_from, start_until=start_until,
                    term_months=term_months, valid_from=self._date,
                    valid_until=self._date + timedelta(days=1),
                    min_volume=min_vol, limit_volume=max_vol, price=price)
