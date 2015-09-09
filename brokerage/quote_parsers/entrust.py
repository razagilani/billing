from tablib import formats

from brokerage.quote_parser import _assert_true, QuoteParser, \
    excel_number_to_datetime
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class DirectEnergyMatrixParser(QuoteParser):
    """Parser for Entrust spreadsheet.
    """
    FILE_FORMAT = formats.xls

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
        'Daily Matrix Price',
    ]
    EXPECTED_CELLS = [
        (0, 1, 0, 'Direct Energy HQ - Daily Matrix Price Report'),
        (0, HEADER_ROW, 0, 'Contract Start Month'),
        (0, HEADER_ROW, 1, 'State'),
        (0, HEADER_ROW, 2, 'Utility'),
        (0, HEADER_ROW, 3, 'Zone'),
        (0, HEADER_ROW, 4, r'Rate Code\(s\)'),
        (0, HEADER_ROW, 5, 'Product Special Options'),
        (0, HEADER_ROW, 6, 'Billing Method'),
        (0, HEADER_ROW, 7, 'Term'),
    ]
    DATE_CELL = (0, 3, 0, 'as of (\d+/\d+/\d+)')

    EXPECTED_ENERGY_UNIT = unit_registry.MWh

    def _extract_quotes(self):
        pass
