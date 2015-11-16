"""Code related to getting data out of Excel spreadsheets.
"""
import re

from tablib import formats, Databook

from brokerage.validation import _assert_match
from core.exceptions import BillingError, ValidationError


def parse_number(string):
    """Convert number string into a number.
    :param string: number string formatted for American humans (with commas)
    :return: int (if the number is really an integer) or float
    """
    result = float(string.replace(',', ''))
    if result == round(result):
        return int(result)
    return result


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
            start = cls.col_letter_to_index(start)
        if isinstance(stop, basestring):
            stop = cls.col_letter_to_index(stop)
        if inclusive:
            stop += 1
        return range(start, stop, step)

    @classmethod
    def col_letter_to_index(cls, letter):
        """
        :param letter: a spreadsheet column "letter" string, which can be A-Z
        or a multiple letters like (AA-AZ, BA-BZ...), case insensitive
        :return index of spreadsheet column (int)
        """
        result = sum((26 ** i) * (ord(c) - ord('a') + 1) for i, c in
                    enumerate(reversed(letter.lower()))) - 1
        if result < 0:
            raise ValueError('Invalid column letter "%s"' % letter)
        return result

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
            return self._databook.sheets()[sheet_number_or_title]
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
        x = col if isinstance(col, int) else self.col_letter_to_index(col)
        try:
            value = self._get_cell(sheet, x, y)
        except IndexError:
            raise ValidationError('No cell (%s, %s)' % (row, col))

        def get_neighbor_str():
            result = ''
            # clockwise: left up right down
            for direction, nx, ny in [('up', x, y - 1), ('down', x, y + 1),
                                      ('left', x - 1, y), ('right', x + 1, y)]:
                try:
                    nvalue = self._get_cell(sheet, nx, ny)
                except IndexError as e:
                    nvalue = repr(e)
                result += '%s: %s ' % (direction, nvalue)
            return result

        if not isinstance(value, the_type):
            message = ('At (%s, %s, %s), expected type %s, found "%s" with '
                       'type %s. neighbors are %s') % (
                sheet_number_or_title, row, col, the_type, value, type(value),
                get_neighbor_str())
            raise ValidationError(message)
        return value

    def get_matches(self, sheet_number_or_title, row, col, regex, types):
        """Get list of values extracted from the spreadsheet cell at
        (row, col) using groups (parentheses) in a regular expression. Values
        are converted from strings to the given types. Raise ValidationError
        if there are 0 matches or the wrong number of matches or any value
        could not be converted to the expected type.

        Commas are removed from strings before converting to 'int' or 'float'.

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
        # substitute 'parse_number' function for regular int/float
        types = [{int: parse_number, float: parse_number}.get(t, t)
                 for t in types]
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
                raise ValidationError('String "%s" couldn\'t be converted to '
                                      'type %s' % (group, the_type))
            results.append(value)
        if len(results) == 1:
            return results[0]
        return results


