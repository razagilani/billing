"""SQLAlchemy model classes related to the brokerage/Power & Gas business.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Boolean, \
    Float
from sqlalchemy.orm import relationship

from core.model import Base, UtilityAccount
from exc import ValidationError


class BrokerageAccount(Base):
    """Table for storing brokerage-related data associated with a
    UtilityAccount. May represent the same thing as one of the "accounts",
    "customers" etc. in other databases. The current purpose is only to keep
    track of which UtilityAccounts are "brokerage-related".
    """
    __tablename__ = 'brokerage_account'
    utility_account_id = Column(Integer, ForeignKey('utility_account.id'),
                                primary_key=True)
    utility_account = relationship(UtilityAccount)

    def __init__(self, utility_account):
        self.utility_account = utility_account


class Quote(Base):
    """Fixed-price candidate supply contract.
    """
    __tablename__ = 'rate'

    quote_id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('supplier.id'), nullable=False)

    # inclusive start and exclusive end of the period during which the
    # customer can start receiving energy from this supplier
    start_from = Column(DateTime, nullable=False)
    start_until = Column(DateTime, nullable=False)

    # term length in number of utility billing periods
    term_months = Column(Integer, nullable=False)

    # when this quote was received
    date_received = Column(DateTime, nullable=False)

    # inclusive start and exclusive end of the period during which this quote
    # is valid
    valid_from = Column(DateTime, nullable=False)
    valid_until = Column(DateTime, nullable=False)

    # whether this quote involves "POR" (supplier is offering a discount
    # because credit risk is transferred to the utility)
    purchase_of_receivables = Column(Boolean, nullable=False, default=False)

    # fixed price for energy in dollars/energy unit
    price = Column(Float, nullable=False)

    # zone
    zone = Column(String)

    # dual billing
    dual_billing = Column(Boolean, nullable=False)

    # Percent Swing Allowable
    percent_swing_allowable = Column(Float)

    discriminator = Column(String(50), nullable=False)
    __mapper_args__ = {
        'polymorphic_identity': 'quote',
        'polymorphic_on': discriminator,
    }

    MIN_TERM_MONTHS = 1
    MAX_TERM_MONTHS = 36
    MIN_PRICE = .01
    MAX_PRICE = 2.0

    def __init__(self, start_from=None, start_until=None, term_months=None,
                 date_received=None, valid_from=None, valid_until=None,
                 price=None, purchase_of_receivables=None):
        self.start_from = start_from
        self.start_until = start_until
        self.term_months = term_months
        self.date_received = date_received or datetime.utcnow()
        self.valid_from = valid_from
        self.valid_until = valid_until
        self.price = price
        self.purchase_of_receivables = purchase_of_receivables

    def validate(self):
        """Sanity check to catch any values that are obviously wrong.
        """
        conditions = {
            self.start_from < self.start_until: 'start_from >= start_until',
            self.term_months >= self.MIN_TERM_MONTHS and self.term_months <=
                                                         self.MAX_TERM_MONTHS:
                'Expected term_months between %s and %s, found %s' % (
                    self.MIN_TERM_MONTHS, self.MAX_TERM_MONTHS,
                    self.term_months),
            self.valid_from < self.valid_until: 'valid_from >= valid_until',
            self.price >= self.MIN_PRICE and self.price <= self.MAX_PRICE:
                'Expected price between %s and %s, found %s' % (
            self.MIN_PRICE, self.MAX_PRICE, self.price)
        }
        all_errors = [error_message for value, error_message in
                      conditions.iteritems() if not value]
        if all_errors != []:
            raise ValidationError('. '.join(all_errors))

class MatrixQuote(Quote):
    """Fixed-price candidate supply contract that applies to any customer with
    a particular utility, rate class, and annual total energy usage, taken
    from a daily "matrix" spreadsheet.
    """
    __mapper_args__ = {
        'polymorphic_identity': 'matrixquote',
    }

    # lower and upper limits on annual total energy consumption for customers
    # that this quote applies to. nullable because there might be no
    # restrictions on energy usage.
    # (min_volume <= customer's energy consumption < limit_volume)
    min_volume = Column(Float)
    limit_volume = Column(Float)

    def __init__(self, start_from=None, start_until=None, term_months=None,
                 date_received=None, valid_from=None, valid_until=None,
                 price=None, min_volume=None, limit_volume=None,
                 purchase_of_receivables=None):
        super(MatrixQuote, self).__init__(
            start_from=start_from, start_until=start_until,
            term_months=term_months, date_received=date_received,
            valid_from=valid_from, valid_until=valid_until, price=price,
            purchase_of_receivables=purchase_of_receivables)
        self.min_volume = min_volume
        self.limit_volume = limit_volume

    def __str__(self):
        return '\n'.join(['Matrix quote'] +
                         ['%s: %s' % (name, getattr(self, name)) for name in
                          self.column_names()] + [''])