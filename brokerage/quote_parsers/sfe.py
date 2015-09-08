from tablib import formats

from brokerage.quote_parser import _assert_true, QuoteParser, \
    excel_number_to_datetime
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class SFEMatrixParser(QuoteParser):
    """Parser for SFE spreadsheet.
    """
    FILE_FORMAT = formats.xlsx

    # TODO: not updated yet
    HEADER_ROW = 51
    VOLUME_RANGE_ROW = 51
    QUOTE_START_ROW = 52
    STATE_COL = 'B'
    UTILITY_COL = 'C'
    RATE_CLASS_COL = 'E'
    SPECIAL_OPTIONS_COL = 'F'
    TERM_COL = 'H'
    PRICE_START_COL = 8
    PRICE_END_COL = 13

    EXPECTED_SHEET_TITLES = [
        'New York',
        'PA Elec',
        'PA Gas',
        'Maryland',
        'NJ Elec',
        'NJ Gas',
    ]
    EXPECTED_CELLS = [
        ('New York', 2, 'D',
         'NEW YORK ELECTRICITY   \(Pricing Includes GRT & POR\)'),
        ('New York', 2, 'O',
         'NEW YORK NATURAL GAS  \(Pricing Includes GRT & POR\)')
        # TODO...
    ]
    DATE_FILE_NAME_REGEX = 'SFE Pricing Worksheet - ([A-Za-z]+ \d\d? \d\d\d\d)'

    EXPECTED_ENERGY_UNIT = unit_registry.MWh
    # TODO: for the gas parts, the unit is therms

    def _extract_quotes(self):
        pass
