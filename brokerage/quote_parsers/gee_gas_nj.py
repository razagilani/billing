from tablib import formats

from brokerage.pdf_reader import PDFReader
from brokerage.quote_parser import QuoteParser, SpreadsheetReader, \
    StartEndCellDateGetter
from brokerage.validation import _assert_true
from core.exceptions import ValidationError
from core.model.model import GAS
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry

import datetime


"""
Note to self:

For overall strategy - go from top down, left-to-right.

For each table on each page for each of NY and NJ..

make a dict of columns, keys are (something like):

  - 6 Month Col
  - 12 Month Col
  - 18 Month Col
  - 24 Month Col
  - Utility Col
  - Load Type Col
  - Start Date Col

And then find the intra-row offset (in px or whatever it is).


The functions that parse each table for each page, should NOT
actually do the parsing... They sould just pre-populate this dictionary-thing.

Hopefully, this allows identical parsing code but allows for parameterizing it.

"""


# Used as a holder for a namespace object.
class Object(object):
    pass

# Indicates quote cannot be inferred at given coordinates.
class QuoteNotFoundException(Exception):
    pass


class GEEGasNJParser(QuoteParser):
    NAME = 'geegas'

    reader = PDFReader(tolerance=5)

    INDEX_NJ_PAGE1 = {
        'Page': 1,
        'State/Type': (546, 376),
        'Valid Date':(508, 27),
        'Volume': (535, 369),
        6: 454,
        12: 492,
        18: 532,
        24: 571,
        'Utility': 27,
        'Start Date': 105,
        'Load Type': 61,
        'Data Start': 491,
        'Intra Row Delta': 10.2,
        'Rows': 32 + 11,
        'Factor': 16
    }

    def _validate(self):
        for page_number, y, x, regex in [
            # Page 1 "Commercial"
            (1, 508, 27, '[\d]+/[\d]+/[\d]+'),
            (1, 535, 369, '0 - 999 Dth'),
            (1, 546, 376, 'NJ Commercial'),
            (1, 508, 27, 'Utility'),
            (1, 508, 61, 'Load Type'),
            (1, 502, 106, 'Start Date'),
            (1, 524, 544, 'Fixed'),
            (1, 514, 489, 'Term \(Months\)'),

            # Page 2 "Residential" (We ignore this)
            # Page 3 "Large Commercial"
            #(3, 448, 355, 'NJ Large Commercial')
        ]:
            self._reader.get_matches(page_number, y, x, regex, [])

    def _produce_quote(self, info_dict, context, data_start_offset):
        """
        :param info_dict: Dictionary containing offsets and coordinates.
        :param context: Namespace containing fields with the quote's context.
        :param data_start_offset: Pixel offset of the row in question.
        :return: A quote from the given parameters
        """

        # If there is no price at the assumed coordinates, raise the relevant exception
        # This function should always return a MatrixQuote, and if it can't then it should
        # raise an exception. Returning None is not a good way out here.
        try:
            price = self._reader.get_matches(info_dict['Page'],
                                            data_start_offset,
                                            info_dict[context.month_duration],
                                            '(\d+\.\d+)',
                                            str)
        except ValidationError:
            raise QuoteNotFoundException

        # Find a date string in the format of, eg., Mar-15
        start_month_str = self._reader.get_matches(info_dict['Page'],
                                                   data_start_offset,
                                                   info_dict['Start Date'],
                                                   '([a-zA-Z]{3}-[\d]{2})',
                                                   str).strip()

        # Convert this string to a datetime object, since implicitly we assume the first of the month,
        # we create a new string with a hard-coded 1 and then parse that using strptime.
        start_from_date = datetime.datetime.strptime('1 %s' % start_month_str, '%d %b-%y')
        start_until_date = date_to_datetime((Month(start_from_date) + 1).first)

        utility = self._reader.get_matches(info_dict['Page'],
                                           data_start_offset,
                                           info_dict['Utility'],
                                           '([a-zA-Z]+)',
                                           str).strip()

        # For GEE, this is Heating or Non-Heating.
        load_type = self._reader.get_matches(info_dict['Page'],
                                             data_start_offset,
                                             info_dict['Load Type'],
                                             '([-\w]+)',
                                             str).strip()

        # Since quotes price is per Dth, we need to divide by ten
        # in order to convert to price per therm.
        price = float(price)/10.0

        # Every single price quote should have a DISTINCT reference.
        # This is (also) to avoid situations in which the wrong price is attached
        # to some start date and utility.
        unique_file_reference = '%s %s,%s %s,start %s,%d month,%.4f' % (
                self.file_name, context.state_and_type, utility, load_type,
                start_from_date.strftime('%Y-%m-%d'), context.month_duration, price),

        quote = MatrixQuote(
            start_from=start_from_date,
            start_until=start_until_date,
            term_months=context.month_duration,
            valid_from=context.valid_dates[0],
            valid_until=context.valid_dates[1],
            min_volume=context.volumes[0],
            limit_volume=context.volumes[1],
            purchase_of_receivables=False,
            service_type='gas',
            rate_class_alias='GEE-gas-%s' % \
                '-'.join((context.state_and_type, utility, load_type)),
            file_reference=unique_file_reference,
            price=price
        )
        return quote

    def _parse_page(self, info_dict):
        """
        Parse a page in the multipage PDF document. It is assumed that each page takes care of
        one state/service type (e.g., NJ Residential).
        :param info_dict: This contains offsets and other parameters necessary.
        :return: A generator yielding quotes.
        """

        # The valid_for field is always the top-left most element of the FIRST PAGE.
        valid_date_str = self._reader.get_matches(1,
                                                  info_dict['Valid Date'][0],
                                                  info_dict['Valid Date'][1],
                                                  '([\d]{1,2}/[\d]{1,2}/[\d]{4})',
                                                  str).strip()

        # Make valid_until be for the day after.
        valid_from_date = datetime.datetime.strptime(valid_date_str, '%m/%d/%Y')
        valid_until_date = valid_from_date + datetime.timedelta(days=1)

        volume_str = self._reader.get_matches(info_dict['Page'],
                                              info_dict['Volume'][0],
                                              info_dict['Volume'][1],
                                              '(.*)',
                                              str).strip()

        if '0 - 999' in volume_str:
            min_volume, limit_volume = 0, 9999
        elif '1,000 - 5,999' in volume_str:
            min_volume, limit_volume = 10000, 59999
        else:
            raise ValidationError('Unexpected volume ranges')


        # This will return, for example, "NJ Commercial".
        state_and_type = self._reader.get_matches(info_dict['Page'],
                                                  info_dict['State/Type'][0],
                                                  info_dict['State/Type'][1],
                                                  '(.*)',
                                                  str).strip()

        # Generates a list of row offsets that start each row of price data.
        offsets = [info_dict['Data Start'] - (i * info_dict['Intra Row Delta'])
                   for i in xrange(0, info_dict['Rows'])]

        for data_start_offset in offsets:
            # Get only the 6, 12, 18, 24 month columns.
            for month_duration in [key for key in info_dict.keys() if isinstance(key, int)]:
                # Create a simple namespace
                context = Object()
                context.valid_dates = (valid_from_date, valid_until_date)
                context.volumes = (min_volume, limit_volume)
                context.state_and_type = state_and_type
                context.month_duration = month_duration

                yield self._produce_quote(info_dict, context, data_start_offset)

    def _extract_quotes(self):
        """
        Generate all quotes that exist in the file.
        :return:
        """

        # List of all quotes (but may contain duplicates)
        quotes = list()

        # Contains all DISTINCT quotes.
        filtered_quotes = list()

        # Contains only unique file-reference strings
        references = set()

        for quote in self._parse_page(self.INDEX_NJ_PAGE1):
            try:
                quotes.append(quote)
                references.add(quote.file_reference)
            except QuoteNotFoundException:
                # If no quote found, just keep on going.
                pass

        # Removes duplicates
        for quote in quotes:
            if quote.file_reference in references:
                filtered_quotes.append(quote)
                references.remove(quote.file_reference)

        # Yield only distinct quotes.
        for quote in filtered_quotes:
            yield quote
