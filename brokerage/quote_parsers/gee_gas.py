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


class Object(object):
    pass


class GEEGasPDFParser(QuoteParser):
    NAME = 'geegas'

    reader = PDFReader(tolerance=40)

    indexes_nj_p1 = {
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
        'Data Start': 491
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
            self._reader.get_matches(page_number, y, x, regex, [], tolerance=40)

    def _produce_quote(self, info_dict, context, data_start_offset):

        start_month_str = self._reader.get_matches(info_dict['Page'],
                                                   data_start_offset,
                                                   info_dict['Start Date'],
                                                   '([a-zA-Z]{3}-[\d]{2})',
                                                   str,
                                                   tolerance=40).strip()

        start_from_date = datetime.datetime.strptime('1 %s' % start_month_str, '%d %b-%y')
        start_until_date = date_to_datetime((Month(start_from_date) + 1).first)

        utility = self._reader.get_matches(info_dict['Page'],
                                           data_start_offset,
                                           info_dict['Utility'],
                                           '([a-zA-Z]+)',
                                           str,
                                           tolerance=40).strip()

        load_type = self._reader.get_matches(info_dict['Page'],
                                             data_start_offset,
                                             info_dict['Load Type'],
                                             '([-\w]+)',
                                             str,
                                             tolerance=40).strip()

        price= self._reader.get_matches(info_dict['Page'],
                                        data_start_offset,
                                        info_dict[context.month_duration],
                                        '(\d+\.\d+)',
                                        str,
                                        tolerance=40)

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
            file_reference='%s %s,%s,%s' % (
                self.file_name, info_dict['Page'], 0, 0),
            price=float(price)
        )

        return quote

    def _parse_page(self, info_dict):
        valid_date_str = self._reader.get_matches(1,
                                                  info_dict['Valid Date'][0],
                                                  info_dict['Valid Date'][1],
                                                  '([\d]{1,2}/[\d]{1,2}/[\d]{4})',
                                                  str,
                                                  tolerance=40).strip()
        valid_from_date = datetime.datetime.strptime(valid_date_str, '%m/%d/%Y')
        valid_until_date = valid_from_date + datetime.timedelta(days=1)

        volume_str = self._reader.get_matches(info_dict['Page'],
                                              info_dict['Volume'][0],
                                              info_dict['Volume'][1],
                                              '(.*)',
                                              str,
                                              tolerance=40).strip()

        state_and_type = self._reader.get_matches(info_dict['Page'],
                                                  info_dict['State/Type'][0],
                                                  info_dict['State/Type'][1],
                                                  '(.*)',
                                                  str,
                                                  tolerance=40).strip()

        if '0 - 999' in volume_str:
            min_volume, limit_volume = 0, 999 * 10
        elif '1,000 - 5,999' in volume_str:
            min_volume, limit_volume = 1000 * 10, 5999 * 10
        else:
            raise ValidationError('Unknown volume ranges')

        for data_start_offset in [info_dict['Data Start']]:
            for month_duration in [key for key in info_dict.keys() if isinstance(key, int)]:
                # Create a simple namespace
                context = Object()
                context.valid_dates = (valid_from_date, valid_until_date)
                context.volumes = (min_volume, limit_volume)
                context.state_and_type = state_and_type
                context.month_duration = month_duration
                yield self._produce_quote(info_dict, context, data_start_offset)

    def _extract_quotes(self):
        for quote in self._parse_page(self.indexes_nj_p1):
            print quote
            yield quote
