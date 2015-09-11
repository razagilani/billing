from datetime import datetime
from itertools import chain

from tablib import formats

from util.dateutils import date_to_datetime, parse_date
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import QuoteParser, StartEndCellDateGetter, \
    SimpleCellDateGetter
from util.units import unit_registry


class LibertyMatrixParser(QuoteParser):
    """Parser for Liberty Power spreadsheet.
    """
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

    EXPECTED_CELLS = chain.from_iterable([[
        (sheet, 2, 'A', 'EFFECTIVE DATE'),
        (sheet, 2, 'F', 'STATE'),
        (sheet, 2, 'H', 'UTILITY'),
        (sheet, 2, 'K', 'SEGMENT'),
        (sheet, 2, 'N', 'SIZE REQUIREMENT'),
        # TODO: these apply to sub-tables rather than the whole sheet
        (sheet, 5, 'A', 'Utility:'),
        (sheet, 5, 'F', 'Zone:'),
        (sheet, 5, 'K', 'Service Class:'),
        (sheet, 6, 'A', 'Start Date'),
        (sheet, 6, 'B', 'Size Tier'),
        (sheet, 6, 'D', 'FIXED PRICE:  Term in Months'),
        (sheet, 8, 'J', 'Term'),
        (sheet, 8, 'K', 'Price'),
        (sheet, 8, 'L', 'Term'),
        (sheet, 8, 'M', 'Price'),
        (sheet, 6, 'J', 'Fixed Rate - Super Saver'),
    # TODO: include other sheets that have different format
    ] for sheet in ['DC-PEPCO-DC-SMB']])

    EXPECTED_ENERGY_UNIT = unit_registry.MWh

    date_getter = SimpleCellDateGetter(0, 2, 'D', '(\d\d?/\d\d?/\d\d\d\d)')

    def _process_subtable(self, sheet, start_row):
        utility = self._reader.get(sheet, start_row, self.UTILITY_COL, basestring)
        zone = self._reader.get(sheet, start_row, self.ZONE_COL, basestring)
        rate_class = self._reader.get(sheet, start_row, self.RATE_CLASS_COL, basestring)
        rate_class_alias = rate_class

        quote_start_row = start_row + 4
        term_row = start_row + 3

        def row_is_all_blank(row):
            return all(
                [(self._reader.get(sheet, row, col, object) in (None, '')) for
                 col in self._reader.column_range('A', 'H')])

        dates = []
        for row in xrange(quote_start_row, self._reader.get_height(sheet)):
            # blank cell means this is the end of the block
            if row_is_all_blank(row):
                break
            cell_value = self._reader.get(sheet, row, self.START_COL,
                                          basestring)
            if cell_value == '':
                dates.append(dates[-1])
            else:
                start_from = date_to_datetime(parse_date(cell_value))
                dates.append(start_from)

        for row in xrange(quote_start_row, self._reader.get_height(sheet)):
            # blank cell means this is the end of the block
            if row_is_all_blank(row):
                break
            start_from = dates[row - quote_start_row]
            start_until = date_to_datetime((Month(start_from) + 1).first)

            min_vol, limit_vol = self._extract_volume_range(
                sheet, row, self.VOLUME_RANGE_COL,
                '(?P<low>\d+)-(?P<high>\d+) MWh', fudge_low=True,
                fudge_block_size=5)

            for col in self._reader.column_range(self.PRICE_START_COL,
                                                 self.PRICE_END_COL):
                term_months = self._reader.get_matches(sheet, term_row, col,
                                                       '(\d+)', int)
                price = self._reader.get_matches(sheet, row, col, '(.*)', float)

                # TODO: remember to handle rate class ids in caller
                yield MatrixQuote(
                    start_from=start_from, start_until=start_until,
                    term_months=term_months, valid_from=self._valid_from,
                    valid_until=self._valid_until,
                    min_volume=min_vol, limit_volume=limit_vol,
                    purchase_of_receivables=False,
                    rate_class_alias=rate_class_alias, price=price)


    def _extract_quotes(self):
        sheet = 'DC-PEPCO-DC-SMB'
        for quote in self._process_subtable(sheet, 5):
            print quote
            yield quote
