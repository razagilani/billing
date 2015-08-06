"""SQLAlchemy model classes related to the brokerage/Power & Gas business.
"""
from collections import defaultdict
from datetime import datetime
import itertools
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Boolean, \
    Float, Table, func, desc
from sqlalchemy.orm import relationship

from core.model import UtilityAccount, Base, AltitudeSession
from core.model.model import AltitudeBase
from exc import ValidationError
from util.dateutils import date_to_datetime


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

class RateClass(AltitudeBase):
    __tablename__ = 'Rate_Class_View'
    rate_class_id = Column('Rate_Class_ID', Integer, primary_key=True)

class RateClassAlias(AltitudeBase):
    __tablename__ = 'Rate_Class_Alias'
    rate_class_alias_id = Column('Rate_Class_Alias_ID', Integer,
                                 primary_key=True)
    rate_class_id = Column('Rate_Class_ID', Integer)
    rate_class_alias = Column('Rate_Class_Alias', String, nullable=False)


def load_rate_class_aliases():
    """Return a dictionary that maps rate class aliases to corresponding rate
    class IDs.
    """
    session = AltitudeSession()
    q = session.query(RateClassAlias.rate_class_alias,
        RateClass.rate_class_id).join(
        RateClass, RateClass.rate_class_id == RateClassAlias.rate_class_id
    ).order_by(RateClassAlias.rate_class_alias, RateClass.rate_class_id)

    # build dictionary from query results: alias -> list of rate class ids
    result = defaultdict(lambda: [])
    for rate_class_alias, row in itertools.groupby(
            q.all(), key=lambda row: row[0]):
        rate_class_ids = [element[1] for element in row]
        result[rate_class_alias].extend(rate_class_ids)
    return result


def get_quote_status():
    """Return data about how many quotes were received for each supplier.
    """
    s = AltitudeSession()
    today = date_to_datetime(datetime.utcnow().date())
    join_condition = CompanyPGSupplier.company_id == MatrixQuote.supplier_id
    q = s.query(CompanyPGSupplier.name.label('name'),
                MatrixQuote.supplier_id.label(
                    'supplier_id').label('supplier_id'),
                func.max(MatrixQuote.date_received).label('date_received'),
                func.count(MatrixQuote.rate_id).label('total_count')).outerjoin(
        MatrixQuote, join_condition).group_by(
        CompanyPGSupplier.name, MatrixQuote.supplier_id).subquery()
    today = s.query(CompanyPGSupplier.company_id.label('supplier_id'),
                    func.count(MatrixQuote.supplier_id).label('today_count')
                    ).outerjoin(MatrixQuote, join_condition).filter(
        MatrixQuote.date_received >= today).group_by(
        CompanyPGSupplier.company_id, MatrixQuote.supplier_id).subquery()
    return s.query(q.c.name, q.c.supplier_id, q.c.date_received,
                   q.c.total_count, today.c.today_count).select_from(
        q).outerjoin(today, q.c.supplier_id == today.c.supplier_id).order_by(
        desc(q.c.total_count))

class Quote(AltitudeBase):
    """Fixed-price candidate supply contract.
    """
    __tablename__ = 'Rate_Matrix'

    rate_id = Column('Rate_Matrix_ID', Integer, primary_key=True)
    supplier_id = Column('Supplier_Company_ID', Integer,
                         # foreign key to view is not allowed
                         ForeignKey('Company.Company_ID'), nullable=False)

    rate_class_alias = Column('rate_class_alias', String, nullable=False)
    rate_class_id = Column('Rate_Class_ID', Integer, nullable=True)

    # inclusive start and exclusive end of the period during which the
    # customer can start receiving energy from this supplier
    start_from = Column('Earliest_Contract_Start_Date', DateTime, nullable=False)
    start_until = Column('Latest_Contract_Start_Date', DateTime, nullable=False)

    # term length in number of utility billing periods
    term_months = Column('Contract_Term_Months', Integer, nullable=False)

    # when this quote was received
    date_received = Column('Created_On', DateTime, nullable=False)

    # inclusive start and exclusive end of the period during which this quote
    # is valid
    valid_from = Column('valid_from', DateTime, nullable=False)
    valid_until = Column('valid_until', DateTime, nullable=False)

    # whether this quote involves "POR" (supplier is offering a discount
    # because credit risk is transferred to the utility)
    purchase_of_receivables = Column('Purchase_Of_Receivables', Boolean,
                                     nullable=False, server_default='0')

    # fixed price for energy in dollars/energy unit
    price = Column('Supplier_Price_Dollars_KWH_Therm', Float, nullable=False)

    # zone
    zone = Column('Zone', String)

    # dual billing
    dual_billing = Column('Dual_Billing', Boolean, nullable=False,
                          server_default='1')

    # Percent Swing Allowable
    percent_swing = Column('Percent_Swing_Allowable', Float)

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
    min_volume = Column('Minimum_Annual_Volume_KWH_Therm', Float)
    limit_volume = Column('Maximum_Annual_Volume_KWH_Therm', Float)

    MIN_MIN_VOLUME = 0
    MAX_MIN_VOLUME = 2000
    MIN_LIMIT_VOLUME = 25
    MAX_LIMIT_VOLUME = 2000

    def __str__(self):
        return '\n'.join(['Matrix quote'] +
                         ['%s: %s' % (name, getattr(self, name)) for name in
                          self.column_names()] + [''])