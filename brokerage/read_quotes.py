"""Code for reading quote files. Could include both matrix quotes and custom
quotes.
"""
from abc import ABCMeta, abstractmethod
import calendar
import re
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date

from tablib import Databook, formats

from exc import ValidationError, BillingError
from brokerage.brokerage_model import MatrixQuote


# TODO:
# - time zones are ignored but are needed because quote validity times,
# start dates, are specific to customers in a specific time zone
# - make sure all spreadsheet format errors are ValidationErrors,
# not IndexErrors, ValueErrors, etc (might want to use different exceptions
# for validation and errors while extracting quotes)
# - move code for asserting cell contents into superclass


def _assert_true(p):
    if not p:
        raise ValidationError('Assertion failed')


def _assert_equal(a, b):
    if a != b:
        raise ValidationError("Expected %s, found %s" % (a, b))


class QuoteParser(object):
    """Class for parsing a particular quote spreadsheet. This is stateful and
    one instance should be used per file.
    """
    __metaclass__ = ABCMeta

    # tablib submodule that should be used to import data from the spreadsheet
    FILE_FORMAT = None

    # subclasses can set this to use sheet titles to validate the file
    EXPECTED_SHEET_TITLES = None

    @classmethod
    def _get_databook_from_file(cls, quote_file):
        # TODO tablib always chooses the "active" sheet to make a Dataset,
        # but it should actually create a Databook for all sheets
        result = Databook()

        # tablib's "xls" format takes the file contents as a string as its
        # argument, but "xlsx" and others take a file object
        if cls.FILE_FORMAT in [formats.xlsx]:
            cls.FILE_FORMAT.import_book(result, quote_file)
        elif cls.FILE_FORMAT in [formats.xls]:
            cls.FILE_FORMAT.import_book(result, quote_file.read())
        else:
            raise BillingError('Unknown format: %s' % format.__name__)
        return result

    def __init__(self):
        self._databook = None
        self._sheet = None
        self._validated = False

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
        self._validate()
        self._validated = True

    def extract_quotes(self):
        """Yield Quotes extracted from the file. Raises ValidationError if
        the quote file is malformed.
        """
        if not self._validated:
            self.validate()
        return self._extract_quotes()

    @abstractmethod
    def _validate(self):
        # subclasses do validation here
        raise NotImplementedError

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
        Example:
        >>> self._get_matches(1, 2, '(\d+/\d+/\d+)', parse_date)
        >>> self._get_matches(3, 4, r'(\d+) ([A-Za-z])', (int, str))
        """
        if not isinstance(types, (list, tuple)):
            types = [types]
        text = self._get(row, col, basestring)
        m = re.match(regex, text)
        if m is None:
            raise ValidationError('No match for "%s" in "%s"' % (regex, text))
        if len(m.groups()) != len(types):
            raise ValidationError
        results = []
        for group, the_type in zip(m.groups(), types):
            try:
                value = the_type(group)
            except ValueError:
                raise ValidationError
            results.append(value)
        return results


class DirectEnergyMatrixParser(QuoteParser):
    """Parser for Direct Energy spreadsheet.
    """
    FILE_FORMAT = formats.xls

    QUOTE_START_ROW = 50
    DATE_ROW = 1
    DATE_COL = 0
    VOLUME_RANGE_ROW = QUOTE_START_ROW - 1
    PRICE_START_COL = 8
    PRICE_END_COL = 13

    EXPECTED_SHEET_TITLES = [
        'Daily Matrix Price',
    ]

    def _validate(self):
        # note: it does not seem possible to access the first row (what Excel
        # would call row 1, the one that says "Daily Price Matrix") through
        # tablib/xlwt.
        _assert_equal('Direct Energy HQ - Daily Matrix Price Report',
                      self._sheet.headers[0])
        self._get_matches(self.DATE_ROW, self.DATE_COL, r'as of (\d+/\d+/\d+)',
                          parse_date)
        _assert_equal((
            'Contract Start Month',
            'State',
            'Utility',
            'Zone',
            'Rate Code(s)',
            'Product Special Options',
            'Billing Method',
            'Term'
        ), self._sheet[self.QUOTE_START_ROW - 1][:8])

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
        # date at the top of the sheet: validity/expiration date for every
        # quote in this sheet
        the_date = self._get_matches(self.DATE_ROW, self.DATE_COL,
                                     'as of (\d+/\d+/\d+)', parse_date)

        volume_ranges = [self._extract_volume_range(self.VOLUME_RANGE_ROW, col)
                         for col in xrange(self.PRICE_START_COL,
                                           self.PRICE_END_COL + 1)]

        # volume ranges should be contiguous
        for i, vr in enumerate(volume_ranges[:-1]):
            next_vr = volume_ranges[i + 1]
            _assert_equal(vr[1], next_vr[0])

        for row in xrange(self.QUOTE_START_ROW, self._sheet.height):
            # TODO use time zone here
            start_from = self._get(row, 0, datetime)
            end_day = calendar.monthrange(start_from.year, start_from.month)[1]
            start_until = datetime(start_from.year, start_from.month,
                                   end_day) + timedelta(days=1)
            term_months = self._get(row, 6, int)

            for col in xrange(self.PRICE_START_COL, self.PRICE_END_COL + 1):
                min_vol, max_vol = volume_ranges[col - self.PRICE_START_COL]
                price = self._get(row, col, (int, float)) / 100.
                yield MatrixQuote(
                    start_from=start_from, start_until=start_until,
                    term_months=term_months, valid_from=the_date,
                    valid_until=the_date + timedelta(days=1),
                    min_volume=min_vol, limit_volume=max_vol, price=price)
