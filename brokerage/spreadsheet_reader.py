"""Code related to getting quotes out of Excel spreadsheets.
"""
from tablib import formats, Databook

from brokerage.reader import Reader
from core.exceptions import BillingError, ValidationError


class SpreadsheetReader(Reader):
    """A Reader that gets data specifically from spreadsheets.
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

    def __init__(self, file_format):
        """
        :param file_format: tablib submodule that should be used to import
        data from the spreadsheet
        """
        super(SpreadsheetReader, self).__init__()
        self._file_format = file_format
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

    def load_file(self, quote_file):
        """Read from 'quote_file'. May be very slow and take a huge amount of
        memory.
        :param quote_file: file to read from.
        """
        self._databook = self.get_databook_from_file(quote_file,
                                                     self._file_format)

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


