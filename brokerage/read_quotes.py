"""Code for reading quote files. Could include both matrix quotes and custom
quotes.
"""
import calendar
import re
from datetime import datetime, timedelta

from tablib import Databook, formats

from exc import BillingError
from brokerage.brokerage_model import MatrixQuote

# TODO:
# - tests
# - time zones are ignored but are needed because quote validity times,
# start dates, are specific to customers in a specific time zone
# - make sure all spreadsheet format errors are ValidationErrors,
# not IndexErrors, ValueErrors, etc (might want to use different exceptions
# for validation and errors while extracting quotes)
# - extract code for asserting sheet names and cell contents into superclass
# - extract 'get' function and 'sheet' into superclass
# - "sanity check" quote values after extraction, e.g. start/end dates are in
#  order and near each other, volume/price values are reasonable


class ValidationError(BillingError):
    pass


# for validation
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
    @staticmethod
    def _get_databook_from_file(quote_file):
        # TODO tablib always chooses the "active" sheet to make a Dataset,
        # but it should actually create a Databook for all sheets
        result = Databook()
        formats.xlsx.import_book(result, quote_file)
        return result

    def __init__(self):
        self._databook = None
        self._validated = False

    def load_file(self, quote_file):
        """Read from 'quote_file'. May be very slow and take a huge amount of
        memory.
        :param quote_file: file to read from.
        """
        self._databook = self._get_databook_from_file(quote_file)
        self._validated = False

    def validate(self):
        """Raise ValidationError if the file does not match expectations about
        its format. This is supposed to detect format changes or prevent
        reading the wrong file by accident, not to find all possible
        problems the contents in advance.
        """
        assert self._databook is not None
        self._validate()
        self._validated = True

    def extract_quotes(self):
        """Yield Quotes extracted from the file. Raises ValidationError if
        the quote file is malformed.
        """
        if not self._validated:
            self.validate()
        return self._extract_quotes()

    def _validate(self):
        # subclasses do validation here
        raise NotImplementedError

    def _extract_quotes(self):
        # subclasses do extraction here
        raise NotImplementedError


class DirectEnergyMatrixParser(QuoteParser):
    """Parser for Direct Energy spreadsheet.
    """

    QUOTE_START_ROW = 9
    DATE_ROW = 0
    DATE_COL = 10
    VOLUME_RANGE_ROW = 7
    PRICE_START_COL = 8
    PRICE_END_COL = 13

    def _validate(self):
        expected_sheet_titles = [
            'Select',
            'Output',
            'PricingMatrixReport',
            'Mappings',
            'FormInput',
            'LF',
            'Restricted Use'
        ]
        _assert_equal(expected_sheet_titles,
                      [s.title for s in self._databook.sheets()])

        # note: it does not seem possible to access the first row (what Excel
        # would call row 1, the one that says "Daily Price Matrix") through
        # tablib/xlwt.
        relevant_sheet = self._databook.sheets()[1]
        _assert_equal('Date:', relevant_sheet[self.DATE_ROW][8])
        _assert_equal('Annual Volume (MWh)', relevant_sheet[6][8])
        _assert_equal('***** For easier print view, use the filters '
                      'to narrow down the prices displayed ******',
                      relevant_sheet[6][1])
        # TODO: ...

    def _extract_quotes(self):
        sheet = self._databook.sheets()[1]

        def get(row, col, type):
            try:
                value = sheet[row][col]
            except IndexError:
                raise ValidationError('No cell (%s, %s)' % (row, col))
            _assert_true(isinstance(value, type))
            return value

        def _extract_volume_range(row, col):
            # these cells are strings like like "75-149" where "149" really
            # means < 150, so 1 is added to the 2nd number--unless it is the
            # highest volume range, in which case the 2nd number really means
            # what it says.
            text = get(row, col, basestring)
            m = re.match(r'(\d+)-(\d+)', text)
            if m is None:
                raise ValidationError
            low, high = float(m.group(1)), float(m.group(2))
            if col != self.PRICE_END_COL:
                high += 1
            return low, high

        # date at the top of the sheet: validity/expiration date for every
        # quote in this sheet
        the_date = get(self.DATE_ROW, self.DATE_COL, datetime)

        volume_ranges = [_extract_volume_range(self.VOLUME_RANGE_ROW, col)
                         for col in xrange(self.PRICE_START_COL,
                                           self.PRICE_END_COL + 1)]

        # volume ranges should be contiguous
        for i, vr in enumerate(volume_ranges[:-1]):
            next_vr = volume_ranges[i+1]
            _assert_equal(vr[1], next_vr[0])

        for row in xrange(self.QUOTE_START_ROW, sheet.height):
            # TODO use time zone here
            start_from = get(row, 0, datetime)
            end_day = calendar.monthrange(start_from.year, start_from.month)[1]
            start_until = datetime(start_from.year, start_from.month,
                                   end_day) + timedelta(days=1)
            term_months = get(row, 6, int)

            for col in xrange(self.PRICE_START_COL, self.PRICE_END_COL + 1):
                min_vol, max_vol = volume_ranges[col - self.PRICE_START_COL]
                price = get(row, col, (int, float))
                yield MatrixQuote(start_from=start_from,
                                  start_until=start_until,
                                  term_months=term_months,
                                  valid_from=the_date,
                                  valid_until=the_date + timedelta(days=1),
                                  min_volume=min_vol, limit_volume=max_vol,
                                  price=price)


class AEPMatrixParser(QuoteParser):
    pass


if __name__ == '__main__':
    # example usage
    import os
    from core import ROOT_PATH
    path = os.path.join(ROOT_PATH, 'test/test_brokerage/directenergy.xlsm')
    qp = DirectEnergyMatrixParser()
    with open(path, 'rb') as spreadsheet_file:
        qp.load_file(spreadsheet_file)
    qp.validate()
    for quote in qp.extract_quotes():
        print quote

