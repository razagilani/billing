from datetime import datetime
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import Column, ForeignKey, Table
from sqlalchemy.sql.sqltypes import Integer, String, Boolean, DateTime, Date,\
    Float, Interval, Enum
from billing.data.model.orm import Base
from data.model.company import Company
from exc import DatabaseError
from sqlalchemy import event


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

    def __init__(self, distributor, name, active=True):
        self.distributor = distributor
        self.name = name
        self.active = active


class OfferEstimator(Base):
    """Estimates supplier offers"""

    __tablename__ = 'offer_estimator'

    id = Column(Integer, primary_key=True)
    name = Column(String(128))
    discriminator = Column(String(50))
    active = Column(Boolean)

    __mapper_args__ = {'polymorphic_on': discriminator}

    def __init__(self, session, active=True):
        if session.query(self.__class__).first():
            raise DatabaseError("Feed %s already exists" %
                                self.__class__.__name__)
        self.active = active

    def estimate_offers(self, rate_class, use_periods):
        """Returns offers from use periods"""
        raise NotImplementedError()


class CommitmentPeriodEstimator(OfferEstimator):

    def estimate_offers(self, rate_class, use_periods):
        """Returns offers from use periods"""
        raise NotImplementedError()


class TimeRangeEstimator(OfferEstimator):

    def estimate_offers(self, rate_class, use_periods):
        """Returns offers from use periods"""
        raise NotImplementedError()


class Quote(Base):

    __tablename__ = 'quote'
    discriminator = Column(String(50))
    __mapper_args__ = {'polymorphic_on': discriminator}

    id = Column(Integer, primary_key=True)
    rate_class_id = Column(Integer, ForeignKey('rate_class.id'), nullable=False)
    supplier_id = Column(Integer, ForeignKey('supplier.id'), nullable=False)

    activation_period_mean = Column(Interval)
    activation_period_sigma = Column(Interval)
    charge = Column(String(50))  # generation, transmission, etc.
    quote = Column(Float)
    time_inserted = Column(DateTime, server_default=func.now())
    time_issued = Column(DateTime, nullable=False)
    time_expires = Column(DateTime)
    standard_offer = Column(Boolean)
    units = Column(String(50))  # therms or kWh

    rate_class = relationship('RateClass')
    supplier = relationship('Supplier')

    def __init__(self, supplier, rate_class, quote, sos=False,
                 time_issued=None):
        self.supplier = supplier
        self.rate_class = rate_class
        self.quote = quote
        self.sos = sos
        self.time_issued = time_issued


class TimeRangeQuote(Quote):

    start_time = Column(Date)
    end_time = Column(Date)

    def __init__(self,  supplier, rate_class, quote, standard_offer=False,
                 time_issued=None, start_time=None, end_time=None):
        self.start_time = start_time
        self.end_time = end_time
        super(TimeRangeQuote, self).__init__(supplier, rate_class, quote, sos,
                                             time_issued)


class CommitmentPeriodQuote(Quote):

    commitment_period = Column(Interval)

    def __init__(self, supplier, rate_class, quote, sos=False, time_issued=None,
                 start_time=None, end_time=None):
        self.start_time = start_time
        self.end_time = end_time
        super(CommitmentPeriodQuote, self).__init__(supplier, rate_class, quote,
                                                    sos, time_issued)


supplier_offer_quote = Table('supplier_offer_quote', Base.metadata,
    Column('supplier_offer_id', Integer, ForeignKey('supplier_offer.id'),
           nullable=False),
    Column('quote_id', Integer, ForeignKey('quote.id'), nullable=False)
)

class SupplierOffer(Base):
    """An offer from an energy supplier company to a customer, at a specific
    address."""
    __tablename__ = 'supplier_offer'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    address_id = Column(Integer, ForeignKey('address.id'), nullable=False)
    rate_class_id = Column(Integer, ForeignKey('rate_class.id'), nullable=False)
    supplier_id = Column(Integer, ForeignKey('supplier.id'))

    issuer = Column(Enum('broker', 'supplier', name='supplier_offer_source'))
    time_created = Column(DateTime)
    time_expires = Column(DateTime)

    address = relationship("Address", backref="offers")
    rate_class = relationship("RateClass", backref='offers')
    customer = relationship("Customer", backref="offers")

    service_start_date = Column(Date)
    duration = Column(Integer)
    total_cost = Column(Float)
    est_monthly_cost = Column(Float)
    average_rate = Column(Float)

    commitment_period = Column(Interval)
    relevant_quotes = relationship("Quote", secondary=supplier_offer_quote)

    def __init__(self, address, company, customer, rate_class):
        self.address = address
        raise NotImplementedError()

