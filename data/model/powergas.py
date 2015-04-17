from collections import defaultdict
from datetime import datetime, timedelta, date
from itertools import product
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import relationship, backref
#from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import Column, ForeignKey, Table
from sqlalchemy.sql.sqltypes import Integer, String, Boolean, DateTime, Date,\
    Float, Interval, Enum
from data.model.orm import Base, Session
from exc import DatabaseError
from data.model.company import Company
from core.model import Address
import data.model
import logging

log = logging.getLogger(__name__)

class RateClass(Base):
    """Represents a rate class for a utility company"""
    __tablename__ = 'rate_class'

    id = Column(Integer, primary_key=True)
    utility_id = Column(Integer, ForeignKey('company.id'), nullable=False)
    utility = relationship(Company,
                           backref=backref("rate_classes", lazy='dynamic',
                                           cascade="all, delete-orphan"))
    name = Column(String)
    time_inserted = Column(DateTime, server_default=func.now(), nullable=False)
    time_deactivated = Column(DateTime, default=datetime(2999, 12, 31))

    def __init__(self, utility, name):
        self.utility = utility
        self.name = name


class   Quote(Base):
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
    time_expired = Column(DateTime, default=datetime(2999, 12, 31))
    units = Column(Enum('therm', 'kWh', name='supplier_offer_source'),
                    nullable=False)  # therms or kWh
    company_ref = Column(String)

    rate_class = relationship('RateClass')
    company = relationship('Company')

    def __init__(self, company, rate_class, rate, charge, time_issued,
                 company_ref, time_expired=None, standard_offer=None,
                 units=None, custom=False):

        standard_offer = standard_offer if standard_offer is not None else \
            rate_class.utility == company

        units = units if units is not None else \
            'therm' if company.service == 'gas' else \
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
        self.custom = custom


class BlockQuote(Quote):
    """Represents a quote known to be fixed over a specific time range bounded
    by `start_time` and `end_time`. Typically SOS quotes."""

    __mapper_args__ = {'polymorphic_identity': 'block_quote'}

    time_start = Column(DateTime)
    time_end = Column(DateTime)
    month_min = Column(Float)
    month_max = Column(Float)
    escalator = Column(Float)

    MONTH_SECONDS = 2635200.0

    def total_seconds(self):
        return (self.time_end - self.time_start).total_seconds()

    @property
    def month_min_qps(self):
        """Monthly minimum quantity per second"""
        return self.month_min / self.MONTH_SECONDS

    @property
    def month_max_qps(self):
        """Monthly maximum quantity per second"""
        try:
            return self.month_max / self.MONTH_SECONDS
        except TypeError:
            return None

    def __init__(self, time_start, time_end, month_min, month_max, escalator,
                 company, rate_class, rate, charge, time_issued, company_ref,
                 time_expired=None, standard_offer=None, units=None):
        self.time_start = time_start
        self.time_end = time_end
        self.month_min = month_min
        self.month_max = month_max
        self.escalator = escalator
        super(BlockQuote, self).__init__(company, rate_class, rate,
            charge, time_issued, company_ref, time_expired, standard_offer,
            units)

    def term_seconds(self, term_begin, term_end):
        begin = max(self.time_start, term_begin)
        end = min(self.time_end, term_end)
        return max((end - begin).total_seconds(), 0.0)

    def term_cost(self, consumption_qps, term_begin, term_end):
        return self.rate * self.term_consumption(consumption_qps, term_begin,
                                                 term_end)

    def term_consumption(self, consumption_qps, term_begin, term_end):
        """
        Given a `consumption_qps` in quantity / second, and term bounded by
        `term_begin` and `term_end`, compute the total consumption within the
        block_quote.

        :param consumption_qps: Consumption rate in quantity / second
        :param term_begin: the beginning of the term
        :param term_end: the end of the term
        :return: the total consumption within the block quote
        """
        qps = max(self.month_min_qps,
                   min(float('inf') if self.month_max_qps is None else
                       self.month_max_qps, consumption_qps))
        return (qps - self.month_min_qps) * self.term_seconds(term_begin,
            term_end)


class TermQuote(Quote):
    """Represents a quote known to be fixed, starting on the activation_time
    and ending after a specified term. Typically supplier quotes."""

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
    customer_interest_id = Column(Integer, ForeignKey('customer_interest.id'))

    quantity = Column(Float, nullable=False)
    time_start = Column(DateTime, nullable=False)
    time_end = Column(DateTime, nullable=False)
    peak_quantity = Column(Float)
    off_peak_quantity = Column(Float)

    customer_interest = relationship("CustomerInterest", backref=
        backref("use_periods", lazy="dynamic", cascade="all, delete-orphan"))

    def prorated_quantity(self, start, end):
        """
        Computes a prorated quantity from time period bounded by `start`, `end`
        :param start: a `datetime` instance
        :param end: a `datetime` instance
        :return: a `float` representing prorated quantity
        """
        max_start = max(self.time_start, start)
        min_end = min(self.time_end, end)
        return 0 if max_start >= min_end else self.quantity * \
                            (min_end - max_start).total_seconds() / \
                            (self.time_end - self.time_start).total_seconds()

    def total_seconds(self):
        return (self.time_end - self.time_start).total_seconds()

    def __init__(self, quantity, time_start, time_end, peak_quantity=None,
                 off_peak_quantity=None, customer_interest=None):
        self.quantity = quantity
        self.time_start = time_start
        self.time_end = time_end
        self.peak_quantity = peak_quantity
        self.off_peak_quantity = off_peak_quantity
        self.customer_interest = customer_interest

    @classmethod
    def from_csv_row(cls, csv_row):
        """csv_row in format:
         time_start, time_end, quantity
         %Y-%m-%d, %Y-%m-%d, quantity
         """
        start, end, q = csv_row.split(",")
        return cls(float(q),
                   datetime.strptime(start.strip(), "%Y-%m-%d"),
                   datetime.strptime(end.strip(), "%Y-%m-%d"))


class CustomerInterest(Base):
    """Represents a customer interested in receiving offers at a specific
    address, for a specific rate class"""

    __tablename__ = 'customer_interest'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    address_id = Column(Integer, ForeignKey('address.id'), nullable=False)
    rate_class_id = Column(Integer, ForeignKey('rate_class.id'), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey('user.id'))
    last_updated_by_user_id = Column(Integer, ForeignKey('user.id'))

    #relationships
    customer = relationship("Customer", backref="customer_interests")
    address = relationship("Address", backref="customer_interests")
    rate_class = relationship("RateClass", backref='customer_interests')
    created_by_user = relationship('User', backref='customer_interests_created',
                                   foreign_keys=[created_by_user_id])
    updated_by_user = relationship('User',
                                   foreign_keys=[last_updated_by_user_id])

    time_inserted = Column(DateTime, server_default=func.now(), nullable=False)
    time_updated = Column(DateTime, server_default=func.now(),
                          server_onupdate=func.now(), nullable=False)
    time_offers_generated = Column(DateTime)

    def generate_offers(self):
        session = Session.object_session(self)
        session.query(Offer).filter_by(customer_interest=self).\
            filter_by(created_by_user=None).delete()
        session.flush()

        self.time_offers_generated = datetime.now()
        for maker in session.query(OfferMaker).filter_by(active=True).all():
            self.offers.extend(maker.make_offers(self,
                self.time_offers_generated))


    def __init__(self, customer, address, rate_class,
                 created_by_user, use_periods=[]):
        self.customer = customer
        self.address = address
        self.rate_class = rate_class
        self.use_periods = use_periods
        self.created_by_user = created_by_user

    @property
    def best_rate(self):
        br = self.offers.order_by(Offer.total_projected_rate).first()
        if br and br.total_projected_rate is not None:
            return br.total_projected_rate
        return "none"


offer_quote = Table('offer_quote', Base.metadata,
    Column('offer_id', Integer, ForeignKey('offer.id'),
           nullable=False),
    Column('quote_id', Integer, ForeignKey('quote.id'), nullable=False)
)


class Offer(Base):
    """An offer from an energy company to a customer"""
    __tablename__ = 'offer'

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('company.id'), nullable=False)
    customer_interest_id = Column(Integer, ForeignKey('customer_interest.id'))
    created_by_user_id = Column(Integer, ForeignKey('user.id'))

    time_inserted = Column(DateTime, server_default=func.now(), nullable=False)
    term_months = Column(Float)
    term_begin = Column(Date)

    total_projected_cost = Column(Float)
    total_projected_consumption = Column(Float, nullable=False)
    total_projected_rate = Column(Float)


    quotes = relationship("Quote", secondary=offer_quote)
    company = relationship("Company", backref="offers")
    customer_interest = relationship("CustomerInterest",
                                     backref=backref("offers", lazy="dynamic"))
    created_by_user = relationship('User', backref='offers_created')

    @property
    def mean_monthly_consumption(self):
        return self.total_projected_consumption / self.term_months

    @property
    def use_period_days(self):
        return self.use_period_timedelta().days

    def use_period_timedelta(self):
        first = self.use_periods.order_by(UsePeriod.time_start).first()
        last = self.use_periods.order_by(UsePeriod.end_time.desc()).first()
        return last.end_time - first.time_start

    def __init__(self, customer_interest, company, created_by_user, quotes,
                 term_begin, term_months, total_projected_cost,
                 total_projected_consumption):
        self.customer_interest = customer_interest
        self.company = company
        self.created_by_user = created_by_user
        self.quotes = quotes
        self.term_begin = term_begin
        self.term_months = term_months
        self.total_projected_cost = total_projected_cost
        self.total_projected_consumption = total_projected_consumption

        if total_projected_cost is not None:
            self.total_projected_rate = total_projected_cost / \
                                        total_projected_consumption


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
            raise ValueError("Use period time ranges must be contiguous.")

    @staticmethod
    def extrapolate_use_periods(use_periods):
        """Extrapolates 12 months of use period info"""
        sup = sorted(use_periods, key=lambda x: x.time_start)
        print len(sup)

    @staticmethod
    def validate(rate_class, use_periods):
        """Validates at least one use period and that `use_periods` are
        contiguous."""
        if len(use_periods) == 0:
            raise ValueError("Must provide at least one use period.")
        OfferMaker.validate_periods_contiguous(use_periods)


class BlockOfferMaker(OfferMaker):

    __mapper_args__ = {'polymorphic_identity': 'block_offer_maker'}

    @staticmethod
    def compute_term_begin(offerdt):
        """Use the first day of the next month, but if that day is less than
        two weeks from now, then use the first day of the following month.
        """
        nm = offerdt + relativedelta(months=1)
        if (datetime(nm.year, nm.month, 1) - offerdt).days < 14:
            nm = offerdt + relativedelta(months=2)
        return datetime(nm.year, nm.month, 1)

    @staticmethod
    def mean_quantity(use_periods):
        return sum([up.quantity for up in use_periods]) / len(use_periods)

    @staticmethod
    def mean_total_seconds(use_periods):
        return timedelta(seconds=(sum([up.total_seconds() for up in
                         use_periods]) / len(use_periods))).total_seconds()

    @staticmethod
    def mean_quantity_per_second(use_periods):
        return BlockOfferMaker.mean_quantity(use_periods) / \
               BlockOfferMaker.mean_total_seconds(use_periods)

    @staticmethod
    def project_quotes(block_quotes, term_begin, term_end):
        """Projects additional block quotes based on `block_quotes` to cover a
        time range bounded by `term_begin`, `term_end`. The projected quotes
        will each have a duration equal to mean of those in `block_quotes`.

        :param block_quotes: the block quotes to use as a basis for projection
        :param term_begin: the beginning of the projection term
        :param term_end: the end of the projection term
        """
        seconds_in_year = 31557600
        mean_duration = timedelta(seconds=sum([q.total_seconds() for q in
                                            block_quotes]) / len(block_quotes))

        block_quotes.sort(key=lambda x: x.time_start)
        mint = block_quotes[0].time_start
        while mint > term_begin:
            firsts = [q for q in block_quotes if q.time_begin == mint]
            for q in firsts:
                block_quotes.append(BlockQuote(mint - mean_duration, mint,
                    q.month_min, q.month_max, q.escalator, q.company,
                    q.rate_class, q.rate * (1 + q.escalator /
                                    (mean_duration / seconds_in_year)),
                    q.charge, None, None))
            mint = mint - mean_duration

        block_quotes.sort(key=lambda x: x.time_start)
        maxt = block_quotes[-1].time_end
        while maxt < term_end:
            lasts = [q for q in block_quotes if q.time_end == maxt]
            for q in lasts:
                block_quotes.append(BlockQuote(maxt, maxt + mean_duration,
                    q.month_min, q.month_max, q.escalator, q.company,
                    q.rate_class, q.rate * (1 + q.escalator /
                                    (q.total_seconds() / seconds_in_year)),
                    q.charge, None, None))
            maxt = maxt + mean_duration
        return block_quotes

    @staticmethod
    def project_consumption(term_begin, term_months, mean_qps):
        term_end = term_begin + relativedelta(months=term_months)
        return (term_end - term_begin).total_seconds() * mean_qps

    @staticmethod
    def project_cost(term_begin, term_months, mean_qps, quotes):
        term_end = term_begin + relativedelta(months=term_months)
        total_cost = 0.0
        terms_max_qps = dict()
        for quote in quotes:
            k = (quote.time_start, quote.time_end)
            terms_max_qps[k] = max(terms_max_qps.get(k, 0), float('inf') if
                quote.month_max_qps is None else quote.month_max_qps)
            total_cost += quote.term_cost(mean_qps, term_begin, term_end)
        return None if any([mean_qps > qps for qps in terms_max_qps.values()]) \
            else total_cost

    def fetch_project_quotes(self, company, rate_class, term_begin,
                                   term_end, offer_time):
        """Fetches block quotes relevant to the `company` and `rate class`,
        and for the term beginning on `term_begin` and ending on `term_end`.

        If insufficient block quotes exist in the database to wholly cover the
        term, project additional quotes based on those quotes that do exist.

        Time range covered by the projected block quotes will include and may
        exceed the period beginning on `term_begin` and ending on `term_end`.

        :param block_quotes: input block quotes to use for projection
        :param term_begin: a datetime begining the term
        :param term_end: a datetime ending the term
        :return:
        """
        session = Session.object_session(self)
        blq = session.query(BlockQuote).\
            filter_by(rate_class=rate_class).\
            filter_by(company=company).\
            filter(BlockQuote.time_expired > offer_time)

        block_quotes = blq.filter(BlockQuote.time_start < term_end).\
                           filter(BlockQuote.time_end > term_begin).\
                           order_by(BlockQuote.time_start).all()

        if len(block_quotes) == 0:
            fq = blq.filter(BlockQuote.time_end < term_begin).first()
            if fq:
                block_quotes = blq.filter_by(time_end=fq.time_end).all()

        if len(block_quotes) == 0:
            lq = blq.filter(BlockQuote.time_start > term_end).first()
            if lq:
                block_quotes = blq.filter_by(time_begin=lq.time_begin)\
                    .all()

        if len(block_quotes) == 0:
            return []

        return BlockOfferMaker.project_quotes(block_quotes, term_begin,
            term_end)

    def quotes_by_company(self, rate_class, offer_time, term_begin,
                          term_months_lst):
        """Returns a dictionary mapping a tuple (company, term_months) to
        a list of quotes"""
        session = Session.object_session(self)
        companies = session.query(Company).all()
        company_quotes = {}
        for company, term_months in product(companies, term_months_lst):
            term_end = term_begin + relativedelta(months=term_months)
            quotes = self.fetch_project_quotes(company, rate_class,
                        term_begin, term_end, offer_time)
            if len(quotes) > 0:
                company_quotes[(company, term_months)] = quotes
        return company_quotes

    def make_offers(self, customer_interest, offer_time,
                    term_months=[6, 12, 24]):
        """Returns offers from use periods
        :param address: The address of the customer
        :param customer: A :class:`processing.state.Customer` instance
        :param rate_class: A :class:`.RateClass` instance
        :param use_periods: A list of :class:`.UsePeriod` instances
        :param offer_time: The time `datetime` to make the offers,
        """

        OfferMaker.validate(customer_interest.rate_class,
                            customer_interest.use_periods)
        term_begin = BlockOfferMaker.compute_term_begin(offer_time)

        company_quotes = self.quotes_by_company(customer_interest.rate_class,
                                            offer_time, term_begin, term_months)

        mean_qps = BlockOfferMaker.mean_quantity_per_second(
            customer_interest.use_periods)

        offers = []
        for (company, term_months), quotes in company_quotes.iteritems():
            total_projected_consumption = BlockOfferMaker.\
                project_consumption(term_begin, term_months, mean_qps)

            total_projected_cost = BlockOfferMaker.\
                project_cost(term_begin, term_months, mean_qps, quotes)


            offers.append(Offer(customer_interest, company, None, quotes, term_begin, term_months,
                                total_projected_cost, ))
            offers.append(Offer(customer_interest,

                address, company, customer, rate_class,
                                use_periods, [q for q in quotes if q.id
                                              is not None],
                                True if total_projected_cost is None else False,
                                term_begin, term_months, total_projected_cost,
                                total_projected_consumption))
        return offers


class TermOfferMaker(OfferMaker):

    __mapper_args__ = {'polymorphic_identity': 'term_offer_maker'}

    def make_offers(self, address, customer, rate_class, use_periods,
                    offer_time=None):
        """Returns offers from use periods"""
        return []
