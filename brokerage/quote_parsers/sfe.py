from datetime import datetime, time
import re

from tablib import formats

from brokerage.quote_parser import QuoteParser, SpreadsheetReader, \
    StartEndCellDateGetter
from brokerage.validation import _assert_true
from core.exceptions import ValidationError
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class SFEMatrixParser(QuoteParser):
    """Parser for SFE spreadsheet.
    """
    NAME = 'sfe'
    reader = SpreadsheetReader(formats.xlsx)

    HEADER_ROW = 21
    STATE_COL = 'B'
    SERVICE_TYPE_COL = 'C'
    START_DATE_COL = 'D'
    RATE_CLASS_COL = 'E'
    VOLUME_RANGE_COL = 'F'
    TERM_COL_RANGE = SpreadsheetReader.column_range('G', 'K')

    EXPECTED_SHEET_TITLES = [
        'Pricing Worksheet',
    ]
    EXPECTED_CELLS = [
        (0, 2, 'D', 'Commercial Pricing Worksheet'),
        (0, 6, 'B',
         'For Single locations above 2 million kWh/yr please email '
         'supply@sfeenergy\.com for pricing'),

        # broker fees must be 0--otherwise they must be subtracted from prices.
        # somehow, the 0s which should be floats are encoded as times.
        # if they are ever not 0, they might become floats.
        (0, 8, 'B', 'Broker Fees'),
        (0, 9, 'B',
         'Electricty - Enter fee in mils, i.e \$0.003/kWh entered as "3" mils'),
        (0, 9, 'F', time(0, 0, 0)),
        (0, 11, 'B', 'Natural Gas - Enter fee in \$ per therm'),
        (0, 11, 'F', time(0, 0, 0)),

        (0, 18, 'B',
         'To find your applicable rate, utilize the filters on row 21\.'),
        (0, 19, 'B',
         'Electricity and Gas Rates - Rates shown are inclusive of above '
         'broker fee and SUT/GRT where applicable')
        # TODO...
    ]

    date_getter = StartEndCellDateGetter(0, 3, 'D', 4, 'D', None)

    # service type names used by SFE in the spreadsheet
    _ELECTRIC = 'Elec'
    _GAS = 'Gas'
    _SERVICE_NAMES = [_ELECTRIC, _GAS]

    # special constant for determining volume range units by context
    USE_LAST_HIGH_UNIT_FACTOR = object()

    def __init__(self):
        super(SFEMatrixParser, self).__init__()

        # for interpreting volume ranges:
        # each pattern comes with 2 factors to multiply the base unit by,
        # but the base unit itself could be either therms or kWh depending on
        # the service type (gas or electric). there is a separate factor for
        # the low and high values because in some cases they have different
        # effective units.
        # K adds an extra factor of 1000 to the unit; M adds an extra 1 million.
        # and as an added complication, in rows where the high value has an "M",
        # the current row's low unit factor is the same as the previous row's
        # high unit factor (which means this must not occur in the first row).
        # for example, "500" in "500-1M" means 5e5 when preceded by "150-500K",
        # but "1" in "1-2M" means 1e6 when preceded by "500-1M".
        self._volume_range_patterns = [
            # regular expression, low unit factor, high unit factor
            ('(?P<low>\d+)-(?P<high>\d+)K', 1000, 1000),
            ('(?P<low>\d+)-(?P<high>\d+)M',
             # special value means context-dependent factor
             self.USE_LAST_HIGH_UNIT_FACTOR, 1e6),
            ('(?P<low>\d+)K\+', 1000, None),
            ('(?P<low>\d+)M\+', 1e6, None),
        ]

        self._target_units = {'Elec': unit_registry.kWh,
                              'Gas': unit_registry.therm}

    def _extract_quotes(self):
        term_lengths = [
            self.reader.get_matches(0, self.HEADER_ROW, col, '(\d+) mth', int)
            for col in self.TERM_COL_RANGE]

        for row in xrange(self.HEADER_ROW + 1, self.reader.get_height(0) + 1):
            state = self.reader.get(0, row, self.STATE_COL, basestring)
            service_type = self.reader.get(0, row, self.SERVICE_TYPE_COL,
                                           basestring)
            _assert_true(service_type in self._SERVICE_NAMES)
            start_from = self.reader.get(0, row, self.START_DATE_COL, datetime)
            start_until = date_to_datetime((Month(start_from) + 1).first)
            rate_class = self.reader.get(0, row, self.RATE_CLASS_COL,
                                         basestring)
            rate_class_alias = '-'.join([state, rate_class])
            rate_class_ids = self.get_rate_class_ids_for_alias(rate_class_alias)

            # volume range can have different format in each row, and the
            # energy unit depends on both the format of the row and the
            # service type.
            volume_text = self.reader.get(
                0, row, self.VOLUME_RANGE_COL, basestring)
            target_unit = self._target_units[service_type]
            for regex, low_unit_factor, high_unit_factor in \
                    self._volume_range_patterns:
                if re.match(regex, volume_text) is not None:
                    min_vol, limit_vol = self._extract_volume_range(
                        0, row, self.VOLUME_RANGE_COL, regex,
                        expected_unit=target_unit,
                        target_unit=target_unit)
                    # note that 'last_unit_factor' will not exist if this is
                    # the first row; it gets initialized at the end of the
                    # row loop
                    if low_unit_factor is self.USE_LAST_HIGH_UNIT_FACTOR:
                        low_unit_factor = last_unit_factor
                    if min_vol is not None:
                        min_vol *= low_unit_factor
                    if limit_vol is not None:
                        limit_vol *= high_unit_factor
                    break
            else:
                raise ValidationError('Volume range text "%s" did not match '
                                      'any expected pattern' % volume_text)

            for col in self.TERM_COL_RANGE:
                term = term_lengths[col - self.TERM_COL_RANGE[0]]
                price = self.reader.get(0, row, col, object)

                # blank cells say "NA". also, some prices are in cents and some
                # are in dollars; the ones shown in dollars are encoded as
                # times, and i don't know how to convert those into useful
                # numbers, so they are skipped.
                if price == 'NA':
                    continue
                elif isinstance(price, time):
                    continue
                elif isinstance(price, float):
                    # rate class column shows the price unit for gas quotes
                    # priced in dollars. (if unit is not shown, assume it's
                    # cents.)
                    if not (rate_class.strip().endswith(
                            '($/therm)') or rate_class.strip().endswith(
                        '($/ccf)')):
                        price /= 100.
                else:
                    raise ValidationError(
                        'Price at (%s, %s) has unexpected type %s: "%s"' % (
                            row, col, type(price), price))

                for rate_class_id in rate_class_ids:
                    quote = MatrixQuote(
                        start_from=start_from, start_until=start_until,
                        term_months=term, valid_from=self._valid_from,
                        valid_until=self._valid_until, min_volume=min_vol,
                        limit_volume=limit_vol,
                        rate_class_alias=rate_class_alias,
                        purchase_of_receivables=False, price=price,
                        service_type={
                            self._GAS: 'gas',
                            self._ELECTRIC: 'electric'
                        }[service_type],
                        file_reference='%s %s,%s,%s' % (self.file_name, 0, row,
                                                     col))
                    quote.file_reference = (row, col)
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote

            last_unit_factor = high_unit_factor

