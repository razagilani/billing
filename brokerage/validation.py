"""This contains code for validating matrix files and also code for validating
quotes (even though these are not really related).
"""
# TODO: ValidationError should probably be specific to this module,
# not a global thing. this kind of validation doesn't have anything in common
#  with other validation.
import re
from abc import ABCMeta
from datetime import datetime

from core.exceptions import ValidationError
from core.model.model import ELECTRIC, GAS


def _assert_true(p):
    if not p:
        raise ValidationError('Assertion failed')


def _assert_equal(a, b):
    if a != b:
        raise ValidationError("Expected %s, found %s" % (a, b))


def _assert_match(regex, string):
    if not re.match(regex, string):
        raise ValidationError('No match for "%s" in "%s"' % (regex, string))


class MatrixQuoteValidator(object):
    """Checks MatrixQuotes for any obviously-wrong values, to prevent bad
    quotes from being stored.
    """
    __metaclass__ = ABCMeta

    MIN_START_FROM = datetime(2000, 1, 1)
    MAX_START_FROM = datetime(2020, 1, 1)
    MIN_TERM_MONTHS = 1
    MAX_TERM_MONTHS = 48

    # subclasses must override these constants to validate volume ranges
    MIN_MIN_VOLUME = 0
    MAX_MIN_VOLUME = None
    MIN_LIMIT_VOLUME = None
    MAX_LIMIT_VOLUME = None
    MIN_VOLUME_DIFFERENCE = None
    MAX_VOLUME_DIFFERENCE = None

    # subclasses must override these to validate prices
    MIN_PRICE = 0
    MAX_PRICE = None

    @classmethod
    def get_instance(cls, service_type):
        """Return an instance of MatrixQuoteValidator with a concrete class
        chosen according to service_type.
        :param service_type: string: or "electric" or "gas"
        """
        return {
            ELECTRIC: ElectricValidator,
            GAS: GasValidator,
        }[service_type]()

    def validate(self, quote):
        """Raise ValidationError if there are any wrong values in the given
        quote.
        :param quote: MatrixQuote
        """
        conditions = {
            quote.start_from < quote.start_until: 'start_from >= start_until',
            quote.start_from >= self.MIN_START_FROM and quote.start_from <=
                                                        self.MAX_START_FROM:
                'start_from too early: %s' % quote.start_from,
            quote.term_months >= self.MIN_TERM_MONTHS and quote.term_months <=
                                                          self.MAX_TERM_MONTHS:
                'Expected term_months between %s and %s, found %s' % (
                    self.MIN_TERM_MONTHS, self.MAX_TERM_MONTHS,
                    quote.term_months),
            quote.valid_from < quote.valid_until:
                'valid_from %s >= valid_until %s' % (quote.valid_from,
                                                     quote.valid_until),
            quote.price >= self.MIN_PRICE and quote.price <= self.MAX_PRICE:
                'Expected price between %s and %s, found %s' % (
                    self.MIN_PRICE, self.MAX_PRICE, quote.price)
        }
        all_errors = [error_message for value, error_message in
                      conditions.iteritems() if not value]
        if all_errors != []:
            raise ValidationError('. '.join(all_errors))

        # volume-range validation
        # TODO: combine this code with above
        try:
            if quote.min_volume is not None:
                assert quote.min_volume >= self.MIN_MIN_VOLUME, (
                    'min_volume below %s: %s' % (
                        self.MIN_MIN_VOLUME, quote.min_volume))
                assert quote.min_volume <= self.MAX_MIN_VOLUME, (
                    'min_volume above %s: %s' % (
                        self.MAX_MIN_VOLUME, quote.min_volume))
            if quote.limit_volume is not None:
                assert quote.limit_volume >= self.MIN_LIMIT_VOLUME, (
                    'limit_volume below %s: %s' % (
                        self.MIN_LIMIT_VOLUME, quote.limit_volume))
                assert quote.limit_volume <= self.MAX_LIMIT_VOLUME, (
                    'limit_volume above %s: %s' % (
                        self.MAX_LIMIT_VOLUME, quote.limit_volume))
            if None not in (quote.min_volume, quote.limit_volume):
                difference = quote.limit_volume - quote.min_volume
                assert (difference >= self.MIN_VOLUME_DIFFERENCE), (
                    'volume range difference < %s: %s' %
                    (self.MIN_VOLUME_DIFFERENCE, difference))
                assert (quote.limit_volume - quote.min_volume <=
                        self.MAX_VOLUME_DIFFERENCE), (
                    'volume range difference > %s: %s' % (
                        self.MAX_VOLUME_DIFFERENCE, difference))
        except AssertionError as e:
            raise ValidationError(e.message)


class ElectricValidator(MatrixQuoteValidator):
    """Specifically for electricity quotes.
    """
    # normal range is $.03/kWh - $.25/kWh
    MIN_PRICE = .01
    MAX_PRICE = 1.0

    # TODO: replace with narrower electric-specific values
    MAX_MIN_VOLUME = 1e9
    MIN_LIMIT_VOLUME = 25
    MAX_LIMIT_VOLUME = 1e9
    MIN_VOLUME_DIFFERENCE = 0
    MAX_VOLUME_DIFFERENCE = 1e7


class GasValidator(MatrixQuoteValidator):
    """Specifically for gas quotes.
    """
    # normal range is $.25/therm - $1/therm
    MIN_PRICE = .10
    MAX_PRICE = 2.0

    # TODO: replace with narrower gas-specific values
    MAX_MIN_VOLUME = 1e9
    MIN_LIMIT_VOLUME = 25
    MAX_LIMIT_VOLUME = 1e9
    MIN_VOLUME_DIFFERENCE = 0
    MAX_VOLUME_DIFFERENCE = 1e7
