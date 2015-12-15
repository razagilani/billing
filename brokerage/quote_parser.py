"""Framework code for parsing matrix quote files, and related tools. Code for
specific suppliers' matrix formats should go in separate files.
"""
from abc import ABCMeta, abstractmethod
import re
from datetime import datetime, timedelta

from tablib import Databook, formats

from brokerage.reader import Reader
from brokerage.validation import ValidationError, _assert_true, _assert_match, \
    _assert_equal
from brokerage.spreadsheet_reader import SpreadsheetReader
from brokerage.brokerage_model import load_rate_class_aliases
from util.dateutils import parse_datetime, excel_number_to_datetime
from util.units import unit_registry


# TODO:
# - time zones are ignored but are needed because quote validity times,
# start dates, are specific to customers in a specific time zone

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

    def _get_date_from_cell(self, reader, row, col):
        if self._regex is None:
            value = reader.get(self._sheet, row, col, (datetime, int, float))
            if isinstance(value, (int, float)):
                value = excel_number_to_datetime(value)
            return value
        return reader.get_matches(self._sheet, row, col, self._regex,
                                  parse_datetime)

    def get_dates(self, quote_parser):
        # TODO: use of private variable
        valid_from = self._get_date_from_cell(quote_parser.reader, self._row,
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
        valid_until = self._get_date_from_cell(quote_parser.reader,
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
        date_str = match.group(1)
        # fix separator characters in the string so parse_datetime can handle
        # them
        date_str = re.sub('_', '-', date_str)
        valid_from = parse_datetime(date_str)
        return valid_from, valid_from + timedelta(days=1)


class QuoteParser(object):
    """Superclass for classes representing particular matrix file formats.
    """
    __metaclass__ = ABCMeta

    # standardized short name of the format or supplier, used to determine names
    # of StatsD metrics (and potentially other purposes). should be lowercase
    # with no spaces or punctuation, like "directenergy". avoid changing this!
    NAME = None

    # a Reader instance to use for this file type (subclasses should set this)
    reader = None

    # subclasses can set this to use sheet titles to validate the file
    EXPECTED_SHEET_TITLES = None

    # subclassses can fill this with (row, col, value) tuples to assert
    # expected contents of certain cells. if value is a string it is
    # interpreted as a regex (so remember to escape characters like '$').
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
        # name should be defined
        assert isinstance(self.NAME, basestring)

        # reader should be set to a Reader instance by subclass
        assert self.reader is not None
        # TODO: remove '_reader' variable used in subclasses
        self._reader = self.reader

        self._file_name = None

        # whether validation has been done yet
        self._validated = False

        # optional validity date and expiration dates for all quotes (matrix
        # quote files tend have dates in them and are good for one day; some
        # are valid for a longer period of time)
        self._valid_from = None
        self._valid_until = None

        # number of quotes read so far
        self._count = 0

        # mapping of rate class alias to rate class ID, loaded in advance to
        # avoid repeated queries
        self._rate_class_aliases = self._load_rate_class_aliases()

    def get_name(self):
        """Rerturn the short standardized name of the format or supplier that
        this parser is for.
        """
        return self.__class__.get_name()

    def _load_rate_class_aliases(self):
        # allow tests to avoid using the database by overriding this method
        # TODO: using a separate DAO object would be a better way
        return load_rate_class_aliases()

    def load_file(self, quote_file, file_name=None):
        """Read from 'quote_file'. May be very slow and take a huge amount of
        memory.
        :param quote_file: file to read from.
        :param file_name: name of the file, used in some formats to get
        valid_from and valid_until dates for the quotes
        """
        self.reader.load_file(quote_file)
        self._validated = False
        self._count = 0
        self.file_name = file_name
        self._after_load()

    def _after_load(self):
        """This method is executed after the file is loaded, and before it is
        validated. Subclasses can override it to add extra behavior such
        as preparing the Reader with additional data taken from the file.
        """
        pass

    def validate(self):
        """Raise ValidationError if the file does not match expectations about
        its format. This is supposed to detect format changes or prevent
        reading the wrong file by accident, not to find all possible
        problems the contents in advance.
        """
        assert self.reader.is_loaded()
        if self.EXPECTED_SHEET_TITLES is not None:
            _assert_true(set(self.EXPECTED_SHEET_TITLES).issubset(
                set(self.reader.get_sheet_titles())))
        for sheet_number_or_title, row, col, expected_value in \
                self.EXPECTED_CELLS:
            if isinstance(expected_value, basestring):
                text = self.reader.get(sheet_number_or_title, row, col,
                                       basestring)
                _assert_match(expected_value, text)
            else:
                actual_value = self.reader.get(sheet_number_or_title, row, col,
                                               object)
                _assert_equal(expected_value, actual_value)
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
            self._valid_from, self._valid_until = self.date_getter.get_dates(
                self)

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

    def _extract_volume_range(
            self, sheet, row, col, regex, fudge_low=False, fudge_high=False,
            fudge_block_size=10, expected_unit=None, target_unit=None):
        """
        Extract numbers representing a range of energy consumption from a
        spreadsheet cell with a string in it like "150-200 MWh" or
        "Below 50,000 ccf/therms".

        :param sheet: 0-based index (int) or title (string) of the sheet to use
        :param row: row index (int)
        :param col: column index (int) or letter (string)
        :param regex: regular expression string or re.RegexObject containing
        either or both of two named groups, "low" and "high". (Notation is
        "(?P<name>...)": see
        https://docs.python.org/2/library/re.html#regular-expression-syntax)
        If only "high" is included, the low value will be 0. If only "low" is
        given, the high value will be None.
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
        assert set(regex.groupindex.iterkeys()).issubset({'low', 'high'})
        values = self.reader.get_matches(sheet, row, col, regex,
                                         (int,) * regex.groups)
        # TODO: can this be made less verbose?
        if regex.groupindex.keys() == ['low']:
            low, high = values, None
        elif regex.groupindex.keys() == ['high']:
            low, high = None, values
        elif regex.groupindex['low'] == 1:
            low, high = values
        else:
            assert regex.groupindex['high'] == 1
            high, low = values

        if expected_unit is None:
            expected_unit = self.EXPECTED_ENERGY_UNIT
        if target_unit is None:
            target_unit = self.TARGET_ENERGY_UNIT

        if low is not None:
            if fudge_low:
                if low % fudge_block_size == 1:
                    low -= 1
                elif low % fudge_block_size == fudge_block_size - 1:
                    low += 1
            low = int(low * expected_unit.to(target_unit) / target_unit)
        else:
            low = 0
        if high is not None:
            if fudge_high:
                if high % fudge_block_size == 1:
                    high -= 1
                elif high % fudge_block_size == fudge_block_size - 1:
                    high += 1
            high = int(high * expected_unit.to(target_unit) / target_unit)
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
            for col in self.reader.column_range(start_col, end_col)]

        # volume ranges should be contiguous or restarting at 0
        for i, vr in enumerate(result[:-1]):
            next_vr = result[i + 1]
            if not allow_restarting_at_0 or next_vr[0] != 0:
                _assert_equal(vr[1], next_vr[0])

        return result