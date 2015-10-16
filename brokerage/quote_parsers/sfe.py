from datetime import datetime, time
import re

from tablib import formats

from brokerage.quote_parser import _assert_true, QuoteParser, SpreadsheetReader, StartEndCellDateGetter
from core.exceptions import ValidationError
from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from util.units import unit_registry


class SFEMatrixParser(QuoteParser):
    """Parser for SFE spreadsheet.
    """
    FILE_FORMAT = formats.xlsx

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

    def __init__(self):
        super(SFEMatrixParser, self).__init__()

        # for interpreting volume ranges:
        # each pattern comes with 2 factors to multiply the base unit by,
        # but the base unit itself could be either therms or kWh depending on
        # the service type (gas or electric). there is a separate factor for
        # the low and high values because in some cases they have different
        # effective units. (for example, "500-1M" actually means 500 * 1000
        # to 1 million kWh.)
        # K adds an extra factor of 1000 to the unit; M adds an extra 1 million.
        self._volume_range_patterns = [
            # regular expression, low unit factor, high unit factor
            ('(?P<low>\d+)-(?P<high>\d+)K', 1000, 1000),
            ('(?P<low>\d+)-(?P<high>\d+)M', 1000, 1e6),
            ('(?P<low>\d+)K\+', 1000, None),
            ('(?P<low>\d+)M\+', 1e6, None),
        ]

        self._service_names = ['Elec', 'Gas']
        self._target_units = {'Elec': unit_registry.kWh,
                              'Gas': unit_registry.therm}

    def _extract_quotes(self):
        term_lengths = [
            self._reader.get_matches(0, self.HEADER_ROW, col, '(\d+) mth', int)
            for col in self.TERM_COL_RANGE]

        for row in xrange(self.HEADER_ROW + 1, self._reader.get_height(0)):
            state = self._reader.get(0, row, self.STATE_COL, basestring)
            service_type = self._reader.get(0, row, self.SERVICE_TYPE_COL,
                                            basestring)
            _assert_true(service_type in self._service_names)
            start_from = self._reader.get(0, row, self.START_DATE_COL, datetime)
            start_until = date_to_datetime((Month(start_from) + 1).first)
            rate_class = self._reader.get(0, row, self.RATE_CLASS_COL,
                                          basestring)
            rate_class_alias = '-'.join([state, rate_class])
            rate_class_ids = self.get_rate_class_ids_for_alias(rate_class_alias)

            # volume range can have different format in each row, and the
            # energy unit depends on both the format of the row and the
            # service type.
            volume_text = self._reader.get(
                0, row, self.VOLUME_RANGE_COL, basestring)
            target_unit = self._target_units[service_type]
            for regex, low_unit_factor, high_unit_factor in \
                    self._volume_range_patterns:
                if re.match(regex, volume_text) is not None:
                    min_vol, limit_vol = self._extract_volume_range(
                        0, row, self.VOLUME_RANGE_COL, regex,
                        expected_unit=target_unit,
                        target_unit=target_unit)
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
                price = self._reader.get(0, row, col, object)

                # blank cells say "NA". also, some prices are in cents and some
                # are in dollars; the ones shown in dollars are encoded as
                # times, and i don't know how to convert those into useful
                # numbers, so they are skipped.
                if price == 'NA':
                    continue
                elif isinstance(price, time):
                    continue
                elif isinstance(price, float):
                    price /= 100
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
                        purchase_of_receivables=False, price=price)
                    # TODO: rate_class_id should be determined automatically
                    # by setting rate_class
                    if rate_class_id is not None:
                        quote.rate_class_id = rate_class_id
                    yield quote

