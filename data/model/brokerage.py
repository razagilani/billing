from datetime import datetime
from sqlalchemy.orm import relationship, backref
#from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import Column, ForeignKey, Table
from sqlalchemy.sql.sqltypes import Integer, String, Boolean, DateTime, Date,\
    Float, Interval, Enum
from billing.data.model.orm import Base
#from data.model.orm import Session
#from data.model.orm import Session
from exc import DatabaseError
from billing.data.model.company import Company
import billing.data.model


class RateClass(Base):
    """Represents a rate class for a utility company"""
    __tablename__ = 'rate_class'

    id = Column(Integer, primary_key=True)
    utility_id = Column(Integer, ForeignKey('company.id'), nullable=False)
    utility = relationship(Company,
                           backref=backref("rate_classes", lazy='dynamic',
                                           cascade="all, delete-orphan"))
    name = Column(Integer)
    active = Column(Boolean)

    def __init__(self, utility, name, active=True):
        self.utility = utility
        self.name = name
        self.active = active


class Quote(Base):
    """Represents a quote for an energy supplier."""

    __tablename__ = 'quote'
    discriminator = Column(String(50))
    __mapper_args__ = {'polymorphic_on': discriminator}

    id = Column(Integer, primary_key=True)
    rate_class_id = Column(Integer, ForeignKey('rate_class.id'), nullable=False)
    company_id = Column(Integer, ForeignKey('company.id'), nullable=False)

    charge = Column(Enum('generation', 'transmission', 'supply',
        name='company_offer_source'), nullable=False)  # generation, transmission, etc.
    rate = Column(Float, nullable=False)
    time_inserted = Column(DateTime, server_default=func.now(), nullable=False)
    time_issued = Column(DateTime, nullable=False)
    time_expired = Column(DateTime)
    units = Column(Enum('therms', 'kWh', name='supplier_offer_source'),
                    nullable=False)  # therms or kWh
    company_ref = Column(String)

    rate_class = relationship('RateClass')
    company = relationship('Company')

    def __init__(self, company, rate_class, rate, charge, time_issued,
                 company_ref, time_expired=None, standard_offer=None,
                 units=None):

        standard_offer = standard_offer if standard_offer is not None else \
            rate_class.utility == company

        units = units if units is not None else \
            'therms' if company.service == 'gas' else \
            'kWh' if company.service == 'electric' else None

        self.company = company
        self.rate_class = rate_class
        self.rate = rate
        self.charge = charge
        self.time_issued = time_issued
        self.company_ref = company_ref
        self.time_expired = time_expired
        self.standard_offer = standard_offer
        self.units = units


class BlockQuote(Quote):
    """Represents a quote known to be fixed over a specific time range bounded
    by `start_time` and `end_time`."""

    __mapper_args__ = {'polymorphic_identity': 'block_quote'}

    start_time = Column(Date)
    end_time = Column(Date)
    block_min = Column(Float)
    block_max = Column(Float)
    escalator = Column(Float)

    def __init__(self, start_time, end_time, block_min, block_max, escalator,
                 company, rate_class, rate, charge, time_issued, company_ref,
                 time_expired=None, standard_offer=None, units=None):
        self.start_time = start_time
        self.end_time = end_time
        self.block_min = block_min
        self.block_max = block_max
        self.escalator = escalator
        super(BlockQuote, self).__init__(company, rate_class, rate,
            charge, time_issued, company_ref, time_expired, standard_offer,
            units)


class TermQuote(Quote):
    """Represents a quote known to be fixed, starting on the activation_time
    and ending after a specified term."""

    __mapper_args__ = {'polymorphic_identity': 'term_quote'}

    term_months = Column(Float)
    annual_min = Column(Float)
    annual_max = Column(Float)
    service_start_begin = Column(Date)  # service start time within range
    service_start_end = Column(Date)

    def __init__(self, term_months, annual_min, annual_max, service_start_begin,
                 service_start_end, company, rate_class, rate, charge,
                 time_issued, company_ref, time_expires=None,
                 standard_offer=None, units=None):
        self.term_months = term_months
        self.annual_min = annual_min
        self.annual_max = annual_max
        self.service_start_begin = service_start_begin
        self.service_start_end = service_start_end
        super(TermQuote, self).__init__(company, rate_class, rate, charge,
            time_issued, company_ref, time_expires, standard_offer, units)


class UsePeriod(Base):
    """Represents a quantity used over a certain time"""

    __tablename__ = 'use_period'

    id = Column(Integer, primary_key=True)
    offer_id = Column(Integer, ForeignKey('offer.id'))

    quantity = Column(Float, nullable=False)
    time_start = Column(DateTime, nullable=False)
    time_end = Column(DateTime, nullable=False)
    peak_quantity = Column(Float)
    off_peak_quantity = Column(Float)

    offer = relationship("Offer", backref=backref("use_periods", lazy="dynamic",
                                                  cascade="all, delete-orphan"))

    def __init__(self,  quantity, time_start, time_end, peak_quantity=None,
                 off_peak_quantity=None):
        self.quantity = quantity
        self.time_start = time_start
        self.time_end = time_end
        self.peak_quantity = peak_quantity
        self.off_peak_quantity = off_peak_quantity


offer_quote = Table('offer_quote', Base.metadata,
    Column('offer_id', Integer, ForeignKey('offer.id'),
           nullable=False),
    Column('quote_id', Integer, ForeignKey('quote.id'), nullable=False)
)


class Offer(Base):
    """An offer from an energy company to a customer"""
    __tablename__ = 'offer'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    address_id = Column(Integer, ForeignKey('address.id'), nullable=False)
    rate_class_id = Column(Integer, ForeignKey('rate_class.id'), nullable=False)
    company_id = Column(Integer, ForeignKey('company.id'), nullable=False)

    time_inserted = Column(DateTime)
    term_months = Column(Float)
    total_projected_cost = Column(Float)
    total_projected_consumption = Column(Float)

    address = relationship("Address", backref="offers")
    quotes = relationship("Quote", secondary=offer_quote)
    rate_class = relationship("RateClass", backref='offers')
    customer = relationship("Customer", backref="offers")
    company = relationship("Company", backref="offers")

    @property
    def total_projected_rate(self):
        return self.total_projected_cost / self.total_projected_consumption

    @property
    def mean_monthly_consumption(self):
        return self.total_projected_consumption / self.term_months

    @property
    def use_period_days(self):
        return self.use_period_timedelta().days

    def use_period_timedelta(self):
        first = self.use_periods.order_by(UsePeriod.start_time).first()
        last = self.use_periods.order_by(UsePeriod.end_time.desc()).first()
        return last.end_time - first.start_time

    def __init__(self, address, company, customer, rate_class, quotes,
                 use_periods, total_projected_cost, total_projected_consumption):
        self.time_inserted = Column(DateTime,
                                    server_default=func.now(),
                                    nullable=False)
        self.address = address
        self.company = company
        self.customer = customer
        self.rate_class = rate_class
        self.quotes = quotes
        self.use_periods = use_periods
        self.total_projected_cost = total_projected_cost
        self.total_projected_consumption = total_projected_consumption

###OfferMakers###


class OfferMaker(Base):
    """Make supplier offers"""
    __tablename__ = 'offer_maker'

    id = Column(Integer, primary_key=True)
    discriminator = Column(String(200))
    active = Column(Boolean)

    __mapper_args__ = {'polymorphic_on': discriminator}

    def __init__(self, session, active=True):
        if session.query(self.__class__).first():
            raise DatabaseError("Feed %s already exists" %
                                self.__class__.__name__)
        self.active = active

    def estimate_offers(self, rate_class, use_periods, time=None):
        """Returns offers from use periods"""
        raise NotImplementedError()

    @staticmethod
    def total_use(use_periods):
        return sum([u.quantity for u in use_periods])

    @staticmethod
    def validate_periods_contiguous(use_periods):
        periods = sorted(use_periods, key=lambda x: x.time_start)
        teq = lambda a, b: a.time_end == b.time_start
        lxeq = lambda i, ls: teq(ls[i], ls[i+1])
        if not all(lxeq(i, periods) for i in range(len(periods) - 1)):
            raise ValueError("Use period time ranges must be contigous.")

    @staticmethod
    def extrapolate_use_periods(use_periods):
        """Extrapolates 12 months of use period info"""
        sup = sorted(use_periods, key=lambda x: x.time_start)
        print len(sup)

    @staticmethod
    def validate(rate_class, use_periods):
        """Validates the input data"""
        OfferMaker.validate_periods_contiguous(use_periods)

class BlockOfferMaker(OfferMaker):

    __mapper_args__ = {'polymorphic_identity': 'block_offer_maker'}

    def make_offers(self, rate_class, use_periods, time=None):
        """Returns offers from use periods"""
        OfferMaker.validate(rate_class, use_periods)
        session = billing.data.model.Session.object_session(self)
        quotes = session.query(BlockQuote).filter_by(rate_class=rate_class)
        #for quote in quotes.all():
        #    print quote.rate, quote.charge
        self.extrapolate_use_periods(use_periods)
        return []


class TermOfferMaker(OfferMaker):

    __mapper_args__ = {'polymorphic_identity': 'term_offer_maker'}

    def make_offers(self, rate_class, use_periods, time=None):
        """Returns offers from use periods"""
        return []
