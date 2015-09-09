from tablib import formats

from brokerage.quote_parser import _assert_true, QuoteParser, \
    excel_number_to_datetime
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class EntrustMatrixParser(QuoteParser):
    """Parser for Entrust spreadsheet.
    """
    FILE_FORMAT = formats.xlsx

    EXPECTED_SHEET_TITLES = [
        'IL - ComEd Matrix',
        'OH - Duke Matrix',
        'OH - Dayton Matrix',
        'PA - PECO Matrix',
        'PA - PPL Matrix',
        'MD - BGE Matrix',
        'MD - PEPCO Matrix',
        'NJ - JCPL Matrix',
        'NYSEG - A - Matrix',
        'NYSEG - B - Matrix',
        'NYSEG - C - Matrix',
        'NYSEG - D - Matrix',
        'NYSEG - E - Matrix',
        'NYSEG - F - Matrix',
        'NYSEG - G - Matrix',
        'NYSEG - H - Matrix',
        'NYSEG - I - Matrix',
        'NY - NATGRID - A - Matrix',
        'NY - NATGRID - B - Matrix',
        'NY - NATGRID - C - Matrix',
        'NY - NATGRID - D - Matrix',
        'NY - NATGRID - E - Matrix',
        'RG&E - B - Matrix',
        'ConEd - H - Matrix',
        'ConEd - I - Matrix',
        'ConEd - J - Matrix']

    EXPECTED_CELLS = [
        (sheet, 4, 'F', 'Pricing for Commercial Customers')
        for sheet in EXPECTED_SHEET_TITLES]

    DATE_CELL = (0, 3, 0, 'as of (\d+/\d+/\d+)')

    EXPECTED_ENERGY_UNIT = unit_registry.kWh

    def _extract_quotes(self):
        pass
