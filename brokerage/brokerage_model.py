"""SQLAlchemy model classes related to the brokerage/Power & Gas business.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Boolean, \
    Float, Table
from sqlalchemy.orm import relationship

from core.model import UtilityAccount, Base
from core.model.model import AltitudeBase
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


class Company(AltitudeBase):
    __tablename__ = 'Company'
    company_id = Column('Company_ID', Integer, primary_key=True)
    name = Column('Company', String, unique=True)


class CompanyPGSupplier(AltitudeBase):
    """View based on the Company table that includes only companies that are
    suppliers.
    """
    __tablename__ = 'Company_PG_Supplier'
    company_id = Column('Company_ID', Integer, primary_key=True)
    name = Column('Company', String, unique=True)


class Quote(AltitudeBase):
    """Fixed-price candidate supply contract.
    """
    __tablename__ = 'rate'

    rate_id = Column('quote_id', Integer, primary_key=True)
    supplier_id = Column('CompanySupplier_ID', Integer,
                         # foreign key to view is not allowed
                         ForeignKey('Company.Company_ID'), nullable=False)

    rate_class_alias = Column(String)

    # inclusive start and exclusive end of the period during which the
    # customer can start receiving energy from this supplier
    start_from = Column('start_from', DateTime, nullable=False)
    start_until = Column('start_until', DateTime, nullable=False)

    # term length in number of utility billing periods
    term_months = Column('term_months', Integer, nullable=False)

    # when this quote was received
    date_received = Column('date_received', DateTime, nullable=False)

    # inclusive start and exclusive end of the period during which this quote
    # is valid
    valid_from = Column('valid_from', DateTime, nullable=False)
    valid_until = Column('valid_until', DateTime, nullable=False)

    # whether this quote involves "POR" (supplier is offering a discount
    # because credit risk is transferred to the utility)
    purchase_of_receivables = Column('purchase_of_receivables', Boolean,
                                     nullable=False, server_default='0')

    # fixed price for energy in dollars/energy unit
    price = Column('price', Float, nullable=False)

    # zone
    zone = Column('zone', String)

    # dual billing
    dual_billing = Column('dual_billing', Boolean, nullable=False,
                          server_default='1')

    # Percent Swing Allowable
    percent_swing = Column('percent_swing', Float)

    discriminator = Column(String(50), nullable=False)
    __mapper_args__ = {
        'polymorphic_identity': 'quote',
        'polymorphic_on': discriminator,
    }

    MIN_TERM_MONTHS = 1
    MAX_TERM_MONTHS = 36
    MIN_PRICE = .01
    MAX_PRICE = 2.0

    def __init__(self, **kwargs):
        super(Quote, self).__init__(**kwargs)
        if self.date_received is None:
            self.date_received = datetime.utcnow()

    # TODO: validation needs to be extensible for subclasses
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
    min_volume = Column('min_volume', Float)
    limit_volume = Column('limit_volume', Float)

    MIN_MIN_VOLUME = 0
    MAX_MIN_VOLUME = 2000
    MIN_LIMIT_VOLUME = 25
    MAX_LIMIT_VOLUME = 2000

    def __str__(self):
        return '\n'.join(['Matrix quote'] +
                         ['%s: %s' % (name, getattr(self, name)) for name in
                          self.column_names()] + [''])