from tablib import formats
from brokerage.spreadsheet_reader import SpreadsheetReader, \
    SpreadsheetFileConverter
from util.dateutils import date_to_datetime, parse_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import excel_number_to_datetime, QuoteParser, \
    SimpleCellDateGetter
from util.units import unit_registry


class ChampionMatrixParser(QuoteParser):
    """ Parser for Champion Matrix Rates
    """
    NAME = 'champion'
    reader = SpreadsheetReader(formats.xls)

    HEADER_ROW = 13
    VOLUME_RANGE_COL = 'H'
    QUOTE_START_ROW = 14
    QUOTE_END_ROW = 445
    RATE_CLASS_COL = 'F'
    EDC_COL = 'E'
    DESCRIPTION_COL = 'G'
    TERM_START_COL = 'I'
    TERM_END_COL = 'K'
    PRICE_START_COL = 'I'
    PRICE_END_COL = 'K'
    STATE_COL = 'D'
    START_DATE_COL = 'C'

    EXPECTED_SHEET_TITLES = [
        'PA',
        'OH',
        'IL',
        'NJ',
        'MD'
    ]

    date_getter = SimpleCellDateGetter('PA', 8, 'C', None)

    EXPECTED_ENERGY_UNIT = unit_registry.MWh

    def _preprocess_file(self, quote_file, file_name=None):
        return SpreadsheetFileConverter(
            'xls', 'xls:"MS Excel 97"').convert_file(quote_file, file_name)

    def _extract_quotes(self):
        for sheet in self.EXPECTED_SHEET_TITLES:

            for row in xrange(self.QUOTE_START_ROW,
                              self.reader.get_height(sheet)):
                state = self.reader.get(sheet, row, self.STATE_COL,
                                        basestring)
                if state == '':
                    continue

                edc = self.reader.get(sheet, row, self.EDC_COL,
                                      basestring)

                description = self.reader.get(sheet, row, self.DESCRIPTION_COL,
                                              basestring)

                rate_class_name = self.reader.get(sheet, row,
                                                  self.RATE_CLASS_COL, basestring)
                rate_class_alias = '-'.join(
                    [state, edc, rate_class_name, description])

                month_str, year = self.reader.get_matches(sheet, row,
                                                          self.START_DATE_COL,r'(\w+)-(\d\d\d\d)', (str,int))

                start_from = parse_datetime('%s/1/%s' % (month_str,year))

                start_until = date_to_datetime((Month(start_from) + 1).first)

                min_volume, limit_volume = self._extract_volume_range(sheet,
                    row, self.VOLUME_RANGE_COL,
                    r'(?P<low>\d+)-(?P<high>\d+) MWh', fudge_low=True)

                for col in self.reader.column_range(self.TERM_START_COL,
                                                    self.TERM_END_COL):
                    price = float(self.reader.get(sheet, row, col,
                                                  (float, basestring,
                                                   type(None))))/1000

                    term = self.reader.get_matches(
                                            sheet, self.HEADER_ROW, col,
                                            '(\d+) mths', int)

                    for rate_class_id in self.get_rate_class_ids_for_alias(
                            rate_class_alias):
                        quote = MatrixQuote(
                            start_from=start_from, start_until=start_until,
                            term_months=term, valid_from=self._valid_from,
                            valid_until=self._valid_until,
                            min_volume=min_volume, limit_volume=limit_volume,
                            purchase_of_receivables=False, price=price,
                            rate_class_alias=rate_class_alias,
                            service_type='electric',
                            file_reference='%s %s,%s,%s' % (
                                self.file_name, 0, row, col))
                        # TODO: rate_class_id should be determined automatically
                        # by setting rate_class
                        if rate_class_id is not None:
                            quote.rate_class_id = rate_class_id
                        yield quote
