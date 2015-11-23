from datetime import datetime
from itertools import chain

from tablib import formats
from brokerage.spreadsheet_reader import SpreadsheetReader
from brokerage.validation import _assert_equal

from util.dateutils import date_to_datetime, parse_date
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import QuoteParser, SimpleCellDateGetter
from core.exceptions import ValidationError
from util.units import unit_registry


class PriceQuoteCell(object):
    """ Represents a cell containing a price. The generate_quote function contains the instructions
    necessary to fetch all other data necesssary to produce the quote.
    """

    def __init__(self, matrix_parser, reader, sheet, row, col, rate_class_alias):
        self.matrix_parser = matrix_parser
        self.reader = reader
        self.sheet = sheet
        self.row = row
        self.col = col
        self.rate_class_alias = rate_class_alias

    def generate_quote(self, ):
        raise NotImplemented


class SuperSaverPriceCell(PriceQuoteCell):
    """ Represents a price in the "Super Saver" columns.
    """

    def __init__(self, matrix_parser, reader, sheet, row, col, rate_class_alias):
        super(self.__class__, self).__init__(matrix_parser, reader, sheet, row, col, rate_class_alias)

    def generate_quote(self):
        price = self.reader.get(self.sheet, self.row, self.col, basestring)
        price = float(price)

        # Fetch Term (in months). This is at a known cell.
        term_months = self.reader.get(self.sheet, self.row, self.col - 1, basestring)
        term_months = int(term_months)

        # Fetch usage tier - Handle special case if cell contains "No Price Tier" first.
        if self.reader.get(self.sheet, self.row,
                            self.matrix_parser.VOLUME_RANGE_COL, basestring) == 'No Price Tier':
            min_vol, limit_vol = 0, self.matrix_parser.LIBERTY_KWH_LIMIT
        else:
            min_vol, limit_vol = self.matrix_parser._extract_volume_range(
                self.sheet, self.row, self.matrix_parser.VOLUME_RANGE_COL,
                '(?P<low>\d+)-(?P<high>\d+) MWh', fudge_low=True,
                fudge_block_size=5)

        # Fetch start date. This has to be found.
        est_date_row = self.row
        while self.reader.get(self.sheet, est_date_row,
                              self.matrix_parser.START_COL, basestring) == '':
            est_date_row = est_date_row - 1

        start_from = date_to_datetime(parse_date(
            self.reader.get(self.sheet, est_date_row,
                            self.matrix_parser.START_COL, basestring)))
        start_until = date_to_datetime((Month(start_from) + 1).first)

        return MatrixQuote(
            start_from=start_from, start_until=start_until,
            term_months=term_months, valid_from=self.matrix_parser._valid_from,
            valid_until=self.matrix_parser._valid_until,
            min_volume=min_vol, limit_volume=limit_vol,
            purchase_of_receivables=False,
            rate_class_alias=self.rate_class_alias, price=price,
            service_type='electric')


class NormalPriceCell(PriceQuoteCell):
    """ Represents a price quote in the normal fixed-rate quote columns.
    """

    def __init__(self, matrix_parser, reader, sheet, row, col, rate_class_alias):
        super(self.__class__, self).__init__(matrix_parser, reader, sheet, row, col, rate_class_alias)

    def generate_quote(self):
        price = self.reader.get(self.sheet, self.row, self.col, basestring)
        price = float(price)

        # Fetch Term (in months). Ugh, while(True). Maybe find a way around this.
        # Keep going up, bypassing floats, until you get an int. Raise exception if
        # you find anything else.
        est_term_row = self.row
        while True:
            cell_val = self.reader.get(self.sheet, est_term_row, self.col, basestring)
            try:
                month_term = float(cell_val)

                if month_term.is_integer():
                    term_months = int(month_term)
                    break
                else:
                    # This is just another price, keep going up
                    est_term_row = est_term_row - 1
            except ValueError:
                raise ValidationError('Expected integer indicating months, but got %s' % cell_val)

        # Fetch usage tier
        if self.reader.get(self.sheet, self.row,
                            self.matrix_parser.VOLUME_RANGE_COL, basestring) == 'No Price Tier':
            min_vol, limit_vol = 0, self.matrix_parser.LIBERTY_KWH_LIMIT
        else:
            min_vol, limit_vol = self.matrix_parser._extract_volume_range(
                self.sheet, self.row, self.matrix_parser.VOLUME_RANGE_COL,
                '(?P<low>\d+)-(?P<high>\d+) MWh', fudge_low=True,
                fudge_block_size=5)

        # Fetch start date
        est_date_row = self.row
        while self.reader.get(self.sheet, est_date_row,
                              self.matrix_parser.START_COL, basestring) == '':
            est_date_row = est_date_row - 1

        start_from = date_to_datetime(parse_date(
            self.reader.get(self.sheet, est_date_row,
                            self.matrix_parser.START_COL, basestring)))
        start_until = date_to_datetime((Month(start_from) + 1).first)

        return MatrixQuote(
            start_from=start_from, start_until=start_until,
            term_months=term_months, valid_from=self.matrix_parser._valid_from,
            valid_until=self.matrix_parser._valid_until,
            min_volume=min_vol, limit_volume=limit_vol,
            purchase_of_receivables=False,
            rate_class_alias=self.rate_class_alias, price=price)


class LibertyMatrixParser(QuoteParser):
    """Parser for Liberty Power spreadsheet.
    """
    NAME = 'liberty'
    READER_CLASS = SpreadsheetReader

    # TODO: we couldn't open this in its original xlsx format
    # (might be fixed by upgrading openpyxl)
    FILE_FORMAT = formats.xls

    START_COL = 'A'
    UTILITY_COL = 'B'
    VOLUME_RANGE_COL = 'B'
    ZONE_COL = 'G'
    RATE_CLASS_COL = 'M'
    PRICE_START_COL = 'D'
    PRICE_END_COL = 'H'
    LIBERTY_KWH_LIMIT = 2000000

    EXPECTED_SHEET_TITLES = [
        'DC-PEPCO-DC-SMB',
        'DC-PEPCO-DC-SMB-National Green ',
        'DE-DELDE-SMB', u'DE-DELDE-SMB-National Green E',
        'IL-AMEREN-SMB', u'IL-AMEREN-SMB-IL Wind',
        'IL-AMEREN-SMB-National Green E',
        'IL-AMEREN-SOHO', u'IL-AMEREN-SOHO-IL Wind',
        'IL-AMEREN-SOHO-National Green E',
        'IL-COMED-SMB', u'IL-COMED-SMB-IL Wind',
        'IL-COMED-SMB-National Green E', u'IL-COMED-SOHO',
        'IL-COMED-SOHO-IL Wind',
        'IL-COMED-SOHO-National Green E', u'MA-MECO-SMB',
        'MA-MECO-SMB-National Green E', u'MA-MECO-SOHO',
        'MA-MECO-SOHO-National Green E',
        'MA-NSTAR-BOS-SMB',
        'MA-NSTAR-BOS-SMB-National Green',
        'MA-NSTAR-BOS-SOHO',
        'MA-NSTAR-BOS-SOHO-National Gree',
        'MA-NSTAR-CAMB-SMB',
        'MA-NSTAR-CAMB-SMB-National Gree',
        'MA-NSTAR-CAMB-SOHO',
        'MA-NSTAR-CAMB-SOHO-National Gre',
        'MA-NSTAR-COMM-SMB',
        'MA-NSTAR-COMM-SMB-National Gree',
        'MA-NSTAR-COMM-SOHO',
        'MA-NSTAR-COMM-SOHO-National Gre',
        'MA-WMECO-SMB', u'MA-WMECO-SMB-National Green E',
        'MA-WMECO-SOHO',
        'MA-WMECO-SOHO-National Green E',
        'MD-ALLEGMD-SMB',
        'MD-ALLEGMD-SMB-National Green E',
        'MD-ALLEGMD-SMB-MD Green', u'MD-ALLEGMD-SOHO',
        'MD-ALLEGMD-SOHO-National Green ',
        'MD-ALLEGMD-SOHO-MD Green', u'MD-BGE-SMB',
        'MD-BGE-SMB-National Green E',
        'MD-BGE-SMB-MD Green', u'MD-BGE-SOHO',
        'MD-BGE-SOHO-National Green E',
        'MD-BGE-SOHO-MD Green', u'MD-DELMD-SMB',
        'MD-DELMD-SMB-National Green E',
        'MD-DELMD-SMB-MD Green', u'MD-PEPCO-MD-SMB',
        'MD-PEPCO-MD-SMB-National Green ',
        'MD-PEPCO-MD-SMB-MD Green', u'MD-PEPCO-MD-SOHO',
        'MD-PEPCO-MD-SOHO-National Green',
        'MD-PEPCO-MD-SOHO-MD Green', u'NJ-ACE-SMB',
        'NJ-ACE-SMB-National Green E', u'NJ-ACE-SOHO',
        'NJ-ACE-SOHO-National Green E', u'NJ-JCP&L-SMB',
        'NJ-JCP&L-SMB-National Green E', u'NJ-JCP&L-SOHO',
        'NJ-JCP&L-SOHO-National Green E', u'NJ-ORNJ-SMB',
        'NJ-ORNJ-SMB-National Green E', u'NJ-PSEG-SMB',
        'NJ-PSEG-SMB-National Green E', u'NJ-PSEG-SOHO',
        'NJ-PSEG-SOHO-National Green E', u'OH-CEI-SMB',
        'OH-CEI-SMB-National Green E', u'OH-CSP-SMB',
        'OH-CSP-SMB-National Green E', u'OH-DAYTON-SMB',
        'OH-DAYTON-SMB-National Green E', u'OH-DUKE-SMB',
        'OH-DUKE-SMB-National Green E', u'OH-DUKE-SOHO',
        'OH-DUKE-SOHO-National Green E', u'OH-OHED-SMB',
        'OH-OHED-SMB-National Green E', u'OH-OHP-SMB',
        'OH-OHP-SMB-National Green E', u'OH-TOLED-SMB',
        'OH-TOLED-SMB-National Green E', u'PA-DUQ-SMB',
        'PA-DUQ-SMB-National Green E',
        'PA-DUQ-SMB-PA Green', u'PA-METED-SMB',
        'PA-METED-SMB-National Green E',
        'PA-METED-SMB-PA Green', u'PA-METED-SOHO',
        'PA-METED-SOHO-National Green E',
        'PA-METED-SOHO-PA Green', u'PA-PECO-SMB',
        'PA-PECO-SMB-National Green E',
        'PA-PECO-SMB-PA Green', u'PA-PECO-SOHO',
        'PA-PECO-SOHO-National Green E',
        'PA-PECO-SOHO-PA Green', u'PA-PENELEC-SMB',
        'PA-PENELEC-SMB-National Green E',
        'PA-PENELEC-SMB-PA Green', u'PA-PENELEC-SOHO',
        'PA-PENELEC-SOHO-National Green ',
        'PA-PENELEC-SOHO-PA Green', u'PA-PENNPR-SMB',
        'PA-PENNPR-SMB-National Green E',
        'PA-PENNPR-SMB-PA Green', u'PA-PENNPR-SOHO',
        'PA-PENNPR-SOHO-National Green E',
        'PA-PENNPR-SOHO-PA Green', u'PA-PPL-SMB',
        'PA-PPL-SMB-National Green E',
        'PA-PPL-SMB-PA Green', u'PA-PPL-SOHO',
        'PA-PPL-SOHO-National Green E',
        'PA-PPL-SOHO-PA Green', u'PA-WPP-SMB',
        'PA-WPP-SMB-National Green E',
        'PA-WPP-SMB-PA Green', u'PA-WPP-SOHO',
        'PA-WPP-SOHO-National Green E',
        'PA-WPP-SOHO-PA Green']

    # instead of the normal EXPECTED_CELLS, which are in only one sheet,
    # these are cells that are the same in all sheets (except "green" ones)
    LIBERTY_EXPECTED_CELLS = [
        (2, 'A', 'EFFECTIVE DATE'),

        # This applies to table (of which there are variable-number per
        # sheet), but we check the existence of only one.
        (5, 'A', 'Utility:'),
        (6, 'A', 'Start Date'),
        (6, 'B', 'Size Tier'),
        (6, 'D', 'FIXED PRICE:  Term in Months'),
    ]

    EXPECTED_ENERGY_UNIT = unit_registry.MWh
    date_getter = SimpleCellDateGetter(0, 2, 'D', '(\d\d?/\d\d?/\d\d\d\d)')

    def _validate(self):
        for sheet in self._reader.get_sheet_titles():
            if not self._is_sheet_green(sheet):
                for (row, col, regexp) in self.LIBERTY_EXPECTED_CELLS:
                    _assert_equal(regexp,
                                  self._reader.get(sheet, row, col, basestring))

                # Make sure every sheet maintains the limit KWH of 2,000,000
                if not any(['%s kWh' % '{:,}'.format(self.LIBERTY_KWH_LIMIT)
                            in (self._reader.get(sheet, 3, col, object) or '')
                            for col in xrange(0, 14)]):
                    raise ValidationError('Size requirements has changed.')

    def _scan_for_tables(self, sheet):
        """
        Scan the sheet, row by row, inferring which ones contain headers for tables
        (which contains price quotes).
        :param sheet:
        :return Yields the rows and rate class alias as a tuple:
        """
        for row in xrange(1, self._reader.get_height(sheet)):
            if 'Utility:' in self._reader.get(sheet, row, self.START_COL, basestring):
                zone, service_class = None, None
                for col in range(0, self._reader.get_width(sheet)):
                    cell_val = self._reader.get(sheet, row, col, basestring)
                    if 'Zone:' == cell_val:
                        zone = self._reader.get(sheet, row, col+1, basestring) or \
                            self._reader.get(sheet, row, col+2, basestring)
                    elif 'Service Class:' == cell_val:
                        service_class = self._reader.get(sheet, row, col+1, basestring) or \
                            self._reader.get(sheet, row, col+2, basestring)

                if not any([zone, service_class]):
                    raise ValidationError('Zone (%s) or Service Class (%s) not found in %s!' % (zone, service_class, sheet))

                rate_class_alias = '%s-%s-%s' % (
                    self._reader.get(sheet, row, 'B', basestring),
                    zone,
                    service_class
                )

                # If see a colon in the rate class alias, that means that it was incorrectly parsed
                if ':' in rate_class_alias:
                    raise ValidationError('Invalid rate class alias %s' % rate_class_alias)

                yield (row, rate_class_alias)

    def _scan_table_headers(self, sheet, table_start_row):
        """
        :param sheet:
        :param table_start_row:
        :return: Tuples containing columns and the type of price in each column (NormalPriceCell or SuperSaverCell)
        """

        col_price_types = list()
        for col in xrange(0, self._reader.get_width(sheet)):
            cell_value = self._reader.get(sheet, table_start_row + 3, col, basestring)

            if cell_value.isdigit():
                col_price_types.append((col, NormalPriceCell))
            elif 'price' in cell_value.lower():
                col_price_types.append((col, SuperSaverPriceCell))
            else:
                # This column then does not indicate that it contains a price quote
                pass

        return col_price_types

    def _is_sheet_green(self, sheet):
        """
        Infers whether the given sheet is for "green" or "wind" quotes, which we
        are not interested in.
        :param sheet:
        :return: Boolean indicating whether sheet is green/wind or not.
        """
        if " green" in sheet.lower() or " wind" in sheet.lower():
            return True
        else:
            return False

    def _extract_quotes(self):
        """Go ahead and extract every quote from the spreadsheet"""

        for sheet in [s for s in self.EXPECTED_SHEET_TITLES if not self._is_sheet_green(s)]:
            for (table_start_row, rate_class_alias) in self._scan_for_tables(sheet):
                for (col, price_type) in self._scan_table_headers(sheet, table_start_row):
                    # row_offset indicates how many rows between start of table and first row
                    # of price data.
                    row_offset = 4
                    while self._reader.get(sheet, table_start_row + row_offset, col, basestring) != '':
                        yield price_type(self, self._reader, sheet, table_start_row + row_offset, col,
                                         rate_class_alias).generate_quote()
                        row_offset += 1
