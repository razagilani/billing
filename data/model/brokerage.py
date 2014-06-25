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


class Estimator(Base):
    """Estimates supplier offers"""

    __tablename__ = 'estimator'

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


class CommitmentPeriodEstimator(Estimator):

    def estimate_offers(self, rate_class, use_periods):
        """Returns offers from use periods"""
        raise NotImplementedError()


class TimeBlockQuoteEstimator(Estimator):

    def estimate_offers(self, rate_class, use_periods):
        """Returns offers from use periods"""
        raise NotImplementedError()


class Quote(Base):
    """Represents a quote for an energy supplier."""

    __tablename__ = 'quote'
    discriminator = Column(String(50))
    __mapper_args__ = {'polymorphic_on': discriminator}

    id = Column(Integer, primary_key=True)
    rate_class_id = Column(Integer, ForeignKey('rate_class.id'), nullable=False)
    supplier_id = Column(Integer, ForeignKey('company.id'), nullable=False)

    charge = Column(Enum('generation', 'transmission', 'supply',
        name='supplier_offer_source'), nullable=False)  # generation, transmission, etc.
    quote = Column(Float, nullable=False)
    time_inserted = Column(DateTime, server_default=func.now(), nullable=False)
    time_issued = Column(DateTime, nullable=False)
    time_expires = Column(DateTime)
    units = Enum('therms', 'kWh', name='supplier_offer_source',
        nullable=False)  # therms or kWh
    supplier_ref = Column(String)

    rate_class = relationship('RateClass')
    supplier = relationship('Supplier')

    def __init__(self, supplier, rate_class, quote, charge, time_issued,
                 supplier_ref, time_expires=None, standard_offer=None,
                 units=None):

        standard_offer = standard_offer if standard_offer is not None else \
            rate_class.utility == supplier

        units = units if units is not None else \
            'therms' if supplier.service is 'gas' else \
            'kWh' if supplier.service is 'electric' else None

        self.supplier = supplier
        self.rate_class = rate_class
        self.quote = quote
        self.charge = charge
        self.time_issued = time_issued
        self.supplier_ref = supplier_ref
        self.time_expires = time_expires
        self.standard_offer = standard_offer
        self.units = units


class TimeBlockQuote(Quote):
    """Represents a quote known to be fixed over a specific time range bounded
    by `start_time` and `end_time`."""

    start_time = Column(Date)
    end_time = Column(Date)
    block_min = Column(Float)
    block_max = Column(Float)

    def __init__(self, start_time, end_time, block_min, block_max,
                 supplier, rate_class, quote, charge, time_issued, supplier_ref,
                 time_expires=None, standard_offer=None, units=None):
        self.start_time = start_time
        self.end_time = end_time
        self.block_min = block_min
        self.block_max = block_max
        super(TimeBlockQuote, self).__init__(supplier, rate_class, quote,
            charge, time_issued, supplier_ref, time_expires, standard_offer,
            units)


class CommitmentPeriodQuote(Quote):
    """Represents a quote known to be fixed over a specific time range starting
    on the activation_time and ending after an interval of length
    commitment_period."""

    commitment_months = Column(Float)

    def __init__(self, commitment_months, supplier, rate_class, quote, charge,
                 time_issued, supplier_ref, time_expires=None,
                 standard_offer=None, units=None):
        self.commitment_months = commitment_months
        super(CommitmentPeriodQuote, self).__init__(supplier, rate_class, quote,
            charge, time_issued, supplier_ref, time_expires, standard_offer,
            units)


supplier_offer_quote = Table('supplier_offer_quote', Base.metadata,
    Column('supplier_offer_id', Integer, ForeignKey('supplier_offer.id'),
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
    supplier_id = Column(Integer, ForeignKey('supplier.id'), nullable=False)

    issuer = Column(Enum('broker', 'supplier', name='supplier_offer_source'))
    time_created = Column(DateTime)
    time_expires = Column(DateTime)

    address = relationship("Address", backref="offers")
    rate_class = relationship("RateClass", backref='offers')
    customer = relationship("Customer", backref="offers")
    supplier = relationship("Supplier", backref="offers")

    service_start_date = Column(Date)
    duration = Column(Integer)
    total_cost = Column(Float)
    est_monthly_cost = Column(Float)
    #projected_monthly_costs
    average_rate = Column(Float)

    commitment_period = Column(Interval)
    relevant_quotes = relationship("Quote", secondary=supplier_offer_quote)

    def __init__(self, address, supplier, customer, rate_class):
        self.address = address
        self.suppiler = supplier
        self.customer = customer
        self.rate_class = rate_class
        raise NotImplementedError()

