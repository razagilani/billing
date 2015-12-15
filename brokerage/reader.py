from abc import ABCMeta
import re
from brokerage.validation import _assert_match
from core.exceptions import ValidationError


def parse_number(string):
    """Convert number string into a number.
    :param string: number string formatted for American humans (with commas)
    :return: int (if the number is really an integer) or float
    """
    result = float(string.replace(',', ''))
    if result == round(result):
        return int(result)
    return result



class Reader(object):
    """Superclass for classes that extract tabular data from files such as
    PDFs or Excel spreadsheets.
    """
    ___metaclass__ = ABCMeta

    def __init__(self):
        self._file_name = None

    def load_file(self, quote_file):
        """Read from 'quote_file'.
        """
        raise NotImplementedError

    def is_loaded(self):
        """:return: True if file has been loaded, False otherwise.
        """
        raise NotImplementedError

    def get(self, page_specifier, y, x, the_type):
        """Return a value extracted from the file at the given coordinates,
        and expect the given type (e.g. int, float, basestring, datetime).
        Raise ValidationError if the cell does not exist or has the wrong type.

        :param page_specifier: a name or number specifies which page or sheet
        to get the value from (dependent on file type)
        :param y: vertical coordinate or row number
        :param x: horizontal coordinate or column number
        :param the_type: expected type of the value
        """
        raise NotImplementedError

    def get_matches(self, page_specifier, y, x, regex, types):
        """Get list of values extracted from the file cell at the given
        coordinates, using groups (parentheses) in a regular expression. Values
        are converted from strings to the given types. Raise ValidationError
        if there are 0 matches or the wrong number of matches or any value
        could not be converted to the expected type.

        Commas are removed from strings before converting to 'int' or 'float'.

        :param page_specifier: a name or number specifies which page or sheet
        to get the value from (dependent on file type)
        :param y: vertical coordinate or row number
        :param x: horizontal coordinate or column number
        :param regex: regular expression string
        :param types: expected type of each match represented as a callable
        that converts a string to that type, or a list/tuple of them whose
        length corresponds to the number of matches.
        :return: resulting value or list of values

        Example:
        >>> self.get_matches(1, 2, '(\d+/\d+/\d+)', parse_date)
        >>> self.get_matches(3, 4, r'(\d+) ([A-Za-z])', (int, str))
        """
        text = self.get(page_specifier, y, x, basestring)
        return self._validate_and_convert_text(regex, text, types)

    def _validate_and_convert_text(self, regex, text, types):
        """Helper method for get_matches. Subclasses can use this by itself
        if they override get_matches to get the text in a different way.
        """
        if not isinstance(types, (list, tuple)):
            types = [types]
        # substitute 'parse_number' function for regular int/float
        types = [{int: parse_number, float: parse_number}.get(t, t)
                 for t in types]
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

