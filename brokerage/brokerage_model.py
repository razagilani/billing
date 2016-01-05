"""SQLAlchemy model classes related to the brokerage/Power & Gas business.
"""
from datetime import datetime
import itertools

from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Boolean, \
    Float, func, desc
from sqlalchemy.orm import relationship

from brokerage.validation import MatrixQuoteValidator
from core.model import UtilityAccount, Base, AltitudeSession, Supplier
from core.model.model import AltitudeBase
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
    # (not using a defaultdict because KeyError is expected when alias is not
    # found)
    result = {}
    for rate_class_alias, row in itertools.groupby(
            q.all(), key=lambda row: row[0]):
        rate_class_ids = [element[1] for element in row]
        result.setdefault(rate_class_alias, [])
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

def count_active_matrix_quotes():
    """Return the number of matrix quotes that are valid right now.
    """
    now = datetime.utcnow()
    s = AltitudeSession()
    return s.query(MatrixQuote).filter(MatrixQuote.valid_from <= now,
                                MatrixQuote.valid_until < now).count()


class MatrixFormat(Base):
    """Represents the format of a matrix file. Related many-1 to
    suppliers (because each supplier may have many formats, even in the same
    email), and 1-1 to QuoteParser classes.

    Could also store any data specific to a file format that needs to be
    user-editable (such as regular expressions for extracting dates from file
    names, so file name changes can be handled without modifying code).
    """
    __tablename__ = 'matrix_format'

    matrix_format_id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('supplier.id'), nullable=False)
    name = Column(String)

    supplier = relationship(Supplier, backref='matrix_formats')

    # regular expression matching names of files that are expected to have
    # this format. should be unique, but may be null if all files from this
    # supplier have this format (for suppliers that send only one file).
    matrix_attachment_name = Column(String)


class Quote(AltitudeBase):
    """Fixed-price candidate supply contract.
    """
    __tablename__ = 'Rate_Matrix'

    rate_id = Column('Rate_Matrix_ID', Integer, primary_key=True)
    supplier_id = Column('Supplier_Company_ID', Integer,
                         # foreign key to view is not allowed
                         ForeignKey('Company.Company_ID'))

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

    # should be "electric" or "gas"--unfortunately SQL Server has no enum type
    service_type = Column(String, nullable=False)

    discriminator = Column(String(50), nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'quote',
        'polymorphic_on': discriminator,
    }

    def __init__(self, **kwargs):
        super(Quote, self).__init__(**kwargs)
        if self.date_received is None:
            self.date_received = datetime.utcnow()

        # pick a MatrixQuoteValidator class based on service type (mandatory)
        assert self.service_type is not None
        assert isinstance(self.term_months, int)
        self._validator = MatrixQuoteValidator.get_instance(self.service_type)

    def validate(self):
        """Sanity check to catch any obviously-wrong values. Raise
        ValidationError if there are any.
        """
        self._validator.validate(self)


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

    # optional string to identify which file and part of the file (eg
    # spreadsheet row and column, or PDF page and coordinates) this quote came
    # from, for troubleshooting
    file_reference = Column('file_reference', String)

    def __str__(self):
        return '\n'.join(['Matrix quote'] +
                         ['%s: %s' % (name, getattr(self, name)) for name in
                          self.column_names()] + [''])


