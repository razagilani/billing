from itertools import chain
from datetime import datetime, timedelta, date
import re
from time import strptime, mktime

from tablib import formats
from brokerage.converters import LibreOfficeFileConverter

from brokerage.quote_parser import QuoteParser
from brokerage.reader import parse_number
from brokerage.spreadsheet_reader import SpreadsheetReader
from core.exceptions import ValidationError
from util.dateutils import date_to_datetime, parse_datetime, parse_date
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class GuttmanGas(QuoteParser):
    """Parser for Guttman Ohio Dominion Gas spreadsheet. This one has energy along the rows and
    time along the columns.
    """
    NAME = 'guttmangas'
    reader = SpreadsheetReader(file_format=formats.xls)

    HEADER_ROW = 6
    RATE_START_ROW = 7
    TITLE_ROW = 3
    TITLE_COL = 'C'
    START_DATE_COL = 'D'
    TERM_COL = 'E'
    VOLUME_RANGE_COL = 'F'
    PRICE_COL = 'G'


    EXPECTED_SHEET_TITLES = [
        'Detail',
        'Summary'
    ]

    DETAIL_SHEET = 1
    SUMMARY_SHEET = 0


    EXPECTED_CELLS = list(chain.from_iterable([
            (sheet, 6, 2, 'Count'),
            (sheet, 6, 3, 'Start'),
            (sheet, 6, 4, 'Term'),
            (sheet, 6, 5, 'Annual kWh'),
            (sheet, 6, 6, r'Price ((?:\(\$/Dth\))|(?:\(\$/Therm\)))')
        ] for sheet in [s for s in EXPECTED_SHEET_TITLES if s != 'Summary']))


    def _preprocess_file(self, quote_file, file_name):
        return LibreOfficeFileConverter(
            'xls', 'xls:"MS Excel 97"').convert_file(quote_file, file_name)


    def _extract_quotes(self):
        title = self._reader.get(self.SUMMARY_SHEET, self.TITLE_ROW,
                                 self.TITLE_COL,
                                 basestring)
        regex = r'(.*)_\(\$/((?:MCF)|(?:CCF)|(?:Therm?))\)'
        rate_class_alias, unit = re.match(regex, title).groups()
        rate_class_alias = 'Guttman-gas-' + rate_class_alias
        if unit == 'MCF':
            expected_unit = unit_registry.Mcf
        elif unit =='CCF' or unit == 'Therm':
            expected_unit = unit_registry.ccf
        valid_from_row = self._reader.get_height(self.SUMMARY_SHEET)
        valid_from = self._reader.get_matches(self.SUMMARY_SHEET,
                                              valid_from_row, 'C',
                                              'Published: (.*)',
                                              parse_datetime)
        #TODO: set valid_until to the same day at 5:00 PM = 22:00 UTC (in the winter)
        valid_until = valid_from + timedelta(days=1)

        for row in xrange(self.RATE_START_ROW,
                          self._reader.get_height(self.DETAIL_SHEET) + 1):
            term = self._reader.get(self.DETAIL_SHEET, row, self.TERM_COL, float)
            min_volume, limit_volume = \
                self._extract_volume_range(self.DETAIL_SHEET, row,
                        self.VOLUME_RANGE_COL,
                        r'(?:EAST|WEST)?(?:_)?(?:MA(?:[\d]+)? [\d]+\: )?'
                        r'(?P<low>[\d,]+)-(?P<high>[\d,]+)'
                        r'(?:_)?(?:MCF|CCF|THERM)?',
                        expected_unit=expected_unit,
                        target_unit=unit_registry.ccf)

            start_from = self._reader.get(self.DETAIL_SHEET, row,
                                          self.START_DATE_COL, unicode)
            start_from = parse_datetime(start_from)

            if start_from is None:
                continue
            start_until = date_to_datetime((Month(start_from) + 1).first)
            price = self._reader.get(self.DETAIL_SHEET, row, self.PRICE_COL, object)
            if (isinstance(price, int) and price == 0) or (isinstance(price, float) and price == 0.0):
                continue
            elif price is None:
                continue
            elif isinstance(price, float) and unit=='MCF':
                # the unit is $/mcf
                price /= 10.
            rate_class_ids = self.get_rate_class_ids_for_alias(
                rate_class_alias)
            for rate_class_id in rate_class_ids:
                quote = MatrixQuote(
                    start_from=start_from, start_until=start_until,
                    term_months=int(term), valid_from=valid_from,
                    valid_until=valid_until,
                    min_volume=min_volume,
                    limit_volume=limit_volume,
                    purchase_of_receivables=False, price=price,
                    rate_class_alias=rate_class_alias,
                    service_type='gas')
                # TODO: rate_class_id should be determined automatically
                # by setting rate_class
                quote.rate_class_id = rate_class_id
                yield quote




