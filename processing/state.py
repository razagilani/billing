#!/usr/bin/python)
"""
Utility functions to interact with state database
"""
import os, sys
import itertools
import datetime
from datetime import timedelta, datetime, date
from itertools import groupby
from operator import attrgetter, itemgetter
import sqlalchemy
from sqlalchemy import Table, Column, MetaData, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import mapper, sessionmaker, scoped_session
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import and_
from sqlalchemy.sql.expression import desc, asc, label
from sqlalchemy.sql.functions import max as sql_max
from sqlalchemy.sql.functions import min as sql_min
from sqlalchemy import func, not_
from sqlalchemy.types import Integer, String, Float, Date, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy
from billing.processing.exceptions import BillStateError, IssuedBillError, NoSuchBillException
sys.stdout = sys.stderr

# Python's datetime.min is too early for the MySQLdb module; including it in a
# query to mean "the beginning of time" causes a strptime failure, so this
# value should be used instead.
MYSQLDB_DATETIME_MIN = datetime(1900,1,1)


# this base class should be extended by all objects representing SQLAlchemy
# tables
Base = declarative_base()

class Customer(Base):
    __tablename__ = 'customer'

    id = Column(Integer, primary_key=True)
    account = Column(String, nullable=False)
    name = Column(String)
    discountrate = Column(Float(asdecimal=False), nullable=False)
    latechargerate = Column(Float(asdecimal=False), nullable=False)
    # this can be null for existing accounts because accounts only use the
    # template document for their first-ever utility bill
    utilbill_template_id = Column(String)

    # email address(es) to receive reebills
    bill_email_recipient = Column(String, nullable=False)

    def get_discount_rate(self):
        return self.discountrate
    def set_discountrate(self, value):
        self.discountrate = value
    def get_late_charge_rate(self):
        return self.latechargerate
    def set_late_charge_rate(self, value):
        self.latechargerate = value

    def __init__(self, name, account, discount_rate, late_charge_rate,
            utilbill_template_id, bill_email_recipient):
        self.name = name
        self.account = account
        self.discountrate = discount_rate
        self.latechargerate = late_charge_rate
        self.utilbill_template_id = utilbill_template_id
        self.bill_email_recipient = bill_email_recipient

    def __repr__(self):
        return '<Customer(name=%s, account=%s, discountrate=%s)>' \
                % (self.name, self.account, self.discountrate)


class ReeBill(Base):
    __tablename__ = 'reebill'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    sequence = Column(Integer, nullable=False)
    issued = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    issue_date = Column(Date)

    # new fields from Mongo
    ree_charge = Column(Float, nullable=False)
    balance_due = Column(Float, nullable=False)
    balance_forward = Column(Float, nullable=False)
    discount_rate = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False)
    late_charge_rate = Column(Float, nullable=False)
    late_charge = Column(Float, nullable=False)
    total_adjustment = Column(Float, nullable=False)
    manual_adjustment = Column(Float, nullable=False)
    payment_received = Column(Float, nullable=False)
    prior_balance = Column(Float, nullable=False)
    ree_value = Column(Float, nullable=False)
    ree_savings = Column(Float, nullable=False)
    email_recipient = Column(String, nullable=True)

    customer = relationship("Customer", backref=backref('reebills',
            order_by=id))

    _utilbill_reebills = relationship('UtilbillReebill', backref='reebill',
            # 'cascade' controls how all insert/delete operations are
            # propagated from the "parent" (ReeBill) to the "child"
            # (UtilbillReebill). UtilbillReebill should be deleted if its
            # ReeBill AND its UtilBill are deleted (though for
            # application-logic reasons the ReeBill will always be deleted
            # first). docs:
            # http://docs.sqlalchemy.org/en/rel_0_8/orm/relationships.html#sqlalchemy.orm.relationship
            # http://docs.sqlalchemy.org/en/rel_0_8/orm/session.html#cascades
            # "delete" here means that if a ReeBill is deleted, its
            # UtilbillReebill is also deleted. it doesn't matter if the
            # UtilbillReebill has a UtilBill, because there is no delete
            # cascade from UtilbillReebill to UtilBill.
            # NOTE: the "utilbill_reebill" table also has ON DELETE CASCADE in
            # the db
            cascade='delete')

    # 'utilbills' is a sqlalchemy.ext.associationproxy.AssociationProxy, which
    # allows users of the ReeBill class to get and set the 'utilbills'
    # attribute (a list of UtilBills) as if ReeBill had a direct relationship
    # to UtilBill, while it is actually an indirect relationship mediated by
    # the UtilBillReebill class (corresponding to the utilbill_reebill table).
    # 'utilbills' is said to be a "view" of the underlying attribute
    # '_utilbill_reebills' (a list of UtilbillReebill objects, which ReeBill
    # has because of the 'backref' in UtilbillReebill.reebill). in other words,
    # if 'r' is a ReeBill, 'r.utilbills' is another way of saying [ur.utilbill
    # for ur in r._utilbill_reebills] (except that it is both readable and
    # writable).
    # 
    # the 1st argument to 'association_proxy' is the name of the attribute of
    # this class containing instances of the intermediate class (UtilbillReebill).
    # the 2nd argument is the name of the property of the intermediate class
    # whose value becomes the value of each element of this property's value.
    #
    # documentation:
    # http://docs.sqlalchemy.org/en/rel_0_8/orm/extensions/associationproxy.html
    # AssociationProxy code:
    # https://github.com/zzzeek/sqlalchemy/blob/master/lib/sqlalchemy/ext/associationproxy.py
    # example code (showing only one-directional relationship):
    # https://github.com/zzzeek/sqlalchemy/blob/master/examples/association/proxied_association.py
    #
    # NOTE on why there is no corresponding 'UtilBill.reebills' attribute: each
    # 'AssociationProxy' has a 'creator', which is a callable that creates a
    # new instance of the intermediate class whenver an instance of the
    # "target" class is appended to the list (in this case, a new instance of
    # 'UtilbillReebill' to hold each UtilBill). the default 'creator' is just
    # the intermediate class itself, which works when that class' constructor
    # has only one argument and that argument is the target class instance. in
    # this case the 'creator' is 'UtilbillReebill' and its __init__ takes one
    # UtilBill as its argument. if there were a bidirectional relationship
    # where 'UtilBill' also had a 'reebills' attribute,
    # UtilbillReebill.__init__ would have to take both a UtilBill and a ReeBill
    # as arguments, so a 'creator' would have to be explicitly specified. for
    # ReeBill it would be something like
    #     creator=lambda u: UtilbillReebill(u, self)
    # and for UtilBill,
    #     creator=lambda r: UtilbillReebill(self, r)
    # but this will not actually work because 'self' is not available in class
    # # scope; there is no instance of UtilBill or ReeBill at the time this
    # code is executed. it also does not work to move the code into __init__
    # and assign the 'utilbills' attribute to a particular ReeBill instance
    # or vice versa. there may be a way to make SQLAlchemy do this (maybe by
    # switching
    # to "classical" class-definition style?) but i decided it was sufficient
    # (for now) to have only a one-directional relationship from ReeBill to
    # UtilBill.
    utilbills = association_proxy('_utilbill_reebills', 'utilbill')

    charges = relationship('ReeBillCharge', backref='reebill')

    def __init__(self, customer, sequence, version=0, discount_rate=None,
                    late_charge_rate=None, utilbills=[]):
        self.customer = customer
        self.sequence = sequence
        self.version = version
        self.issued = 0
        if discount_rate:
            self.discount_rate = discount_rate
        else:
            self.discount_rate = self.customer.discountrate
        if late_charge_rate:
            self.late_charge_rate = late_charge_rate
        else:
            self.late_charge_rate = self.customer.latechargerate

        self.ree_charge = 0
        self.balance_due = 0
        self.balance_forward = 0
        self.due_date = None
        self.late_charge = 0
        self.total_adjustment = 0
        self.manual_adjustment = 0
        self.payment_received = 0
        self.prior_balance = 0
        self.ree_value = 0
        self.ree_savings = 0
        self.email_recipient = None

        # supposedly, SQLAlchemy sends queries to the database whenever an
        # association_proxy attribute is accessed, meaning that if
        # 'utilbills' is set before the other attributes above, SQLAlchemy
        # will try to insert the new row too soon, and fail because many
        # fields are still null but the columns are defined as not-null. this
        # can be fixed by setting 'utilbills' last, but there may be a better
        # solution. see related bug:
        # https://www.pivotaltracker.com/story/show/65502556
        self.utilbills = utilbills

    def __repr__(self):
        return '<ReeBill %s-%s-%s, %s, %s utilbills>' % (
                self.customer.account, self.sequence, self.version, 'issued' if
                self.issued else 'unissued', len(self.utilbills))

    def document_id_for_utilbill(self, utilbill):
        '''Returns the id (string) of the "frozen" utility bill document in
        Mongo corresponding to the given utility bill which is attached to this
        reebill. This will be None if this reebill is unissued.'''
        return next(ubrb.document_id for ubrb in self._utilbill_reebills if
                ubrb.utilbill == utilbill)

    def uprs_id_for_utilbill(self, utilbill):
        '''Returns the id (string) of the "frozen" UPRS document in Mongo
        corresponding to the given utility bill which is attached to this
        reebill. This will be None if this reebill is unissued.'''
        return next(ubrb.uprs_document_id for ubrb in self._utilbill_reebills
                if ubrb.utilbill == utilbill)

    @property
    def total(self):
        '''The sum of all charges on this bill that do not come from other
        bills, i.e. charges that are being charged to the customer's account on
        this bill's issue date. (This includes the late charge, which depends
        on another bill for its value but belongs to the bill on which it
        appears.) This total is what should be used to calculate the adjustment
        produced by the difference between two versions of a bill.'''
        return self.ree_charge + self.late_charge

class UtilbillReebill(Base):
    '''Class corresponding to the "utilbill_reebill" table which represents the
    many-to-many relationship between "utilbill" and "reebill".'''
    __tablename__ = 'utilbill_reebill'

    reebill_id = Column(Integer, ForeignKey('reebill.id'), primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), primary_key=True)
    document_id = Column(String)
    uprs_document_id = Column(String)
    cprs_document_id = Column(String)

    # 'backref' creates corresponding '_utilbill_reebills' attribute in UtilBill.
    # there is no delete cascade in this 'relationship' because a UtilBill
    # should not be deleted when a UtilbillReebill is deleted.
    utilbill = relationship('UtilBill', backref='_utilbill_reebills')

    def __init__(self, utilbill, document_id=None):
        # UtilbillReebill has only 'utilbill' in its __init__ because the
        # relationship goes Reebill -> UtilbillReebill -> UtilBill. NOTE if the
        # 'utilbill' argument is actually a ReeBill, ReeBill's relationship to
        # UtilbillReebill will cause a stack overflow in SQLAlchemy code
        # (without this check).
        assert isinstance(utilbill, UtilBill)

        self.utilbill = utilbill
        self.document_id = document_id

    def __repr__(self):
        return (('UtilbillReebill(utilbill_id=%s, reebill_id=%s, '
                'document_id=...%s, uprs_document_id=...%s, ') % (
                self.utilbill_id, self.reebill_id, self.document_id[-4:],
                self.uprs_document_id[-4:]))


class ReeBillCharge(Base):
    __tablename__ = 'reebill_charge'

    id = Column(Integer, primary_key=True)
    reebill_id = Column(Integer, ForeignKey('reebill.id'), primary_key=True)
    rsi_binding = Column(String, nullable=False)
    description = Column(String, nullable=False)
    # NOTE alternate name is required because you can't have a column called
    # "group" in MySQL
    group = Column(String, name='group_name', nullable=False)
    quantity = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    total = Column(Float, nullable=False)

    def __init__(self, rsi_binding, description, group, quantity, rate, total):
        self.rsi_binding = rsi_binding
        self.description = description
        self.group = group
        self.quantity = quantity
        self.rate = rate
        self.total = total


class UtilBill(Base):
    __tablename__ = 'utilbill'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    state = Column(Integer, nullable=False)
    service = Column(String, nullable=False)
    utility = Column(String, nullable=False)
    rate_class = Column(String, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    total_charges = Column(Float)
    date_received = Column(DateTime)

    # whether this utility bill is considered "done" by the user--mainly
    # meaning that its rate structure and charges are supposed to be accurate
    # and can be relied upon for rate structure prediction
    processed = Column(Integer, nullable=False)

    # _ids of Mongo documents
    document_id = Column(String)
    uprs_document_id = Column(String)
    cprs_document_id = Column(String)

    customer = relationship("Customer", backref=backref('utilbills',
            order_by=id))

    @classmethod
    def validate_utilbill_period(self, start, end):
        '''Raises an exception if the dates 'start' and 'end' are unreasonable
        as a utility bill period: "reasonable" means start < end and (end -
        start) < 1 year.'''
        if start >= end:
            raise ValueError('Utility bill start date must precede end')
        if (end - start).days > 365:
            raise ValueError('Utility billing period lasts longer than a year')

    # utility bill states:
    # 0. Complete: actual non-estimated utility bill.
    # 1. Utility estimated: actual utility bill whose contents were estimated by
    # the utility (and which will be corrected later to become Complete).
    # 2. Skyline estimated: a bill that is known to exist (and whose dates are
    # correct) but whose contents were estimated by Skyline.
    # 3. Hypothetical: Skyline supposes that there is probably a bill during a
    # certain time period and estimates what its contents would be if it
    # existed. Such a bill may not really exist (since we can't even know how
    # many bills there are in a given period of time), and if it does exist,
    # its actual dates will probably be different than the guessed ones.
    # TODO 38385969: not sure this strategy is a good idea
    Complete, UtilityEstimated, SkylineEstimated, Hypothetical = range(4)

    # human-readable names for utilbill states (used in UI)
    _state_descriptions = {
        Complete: 'Final',
        UtilityEstimated: 'Utility Estimated',
        SkylineEstimated: 'Skyline Estimated',
        Hypothetical: 'Missing'
    }

    def __init__(self, customer, state, service, utility, rate_class,
            period_start=None, period_end=None, doc_id=None, uprs_id=None,
            total_charges=0, date_received=None, processed=False, reebill=None):
        '''State should be one of UtilBill.Complete, UtilBill.UtilityEstimated,
        UtilBill.SkylineEstimated, UtilBill.Hypothetical.'''
        # utility bill objects also have an 'id' property that SQLAlchemy
        # automatically adds from the database column
        self.customer = customer
        self.state = state
        self.service = service
        self.utility = utility
        self.rate_class = rate_class
        self.period_start = period_start
        self.period_end = period_end
        self.total_charges = total_charges
        self.date_received = date_received
        self.processed = processed
        self.document_id = doc_id
        self.uprs_document_id = uprs_id

    def state_name(self):
        return self.__class__._state_descriptions[self.state]

    def __repr__(self):
        return ('<UtilBill(customer=<%s>, service=%s, period_start=%s, '
                'period_end=%s, state=%s, %s reebills)>') % (
                self.customer.account, self.service, self.period_start,
                self.period_end, self.state, len(self._utilbill_reebills))

    def is_attached(self):
        return len(self._utilbill_reebills) > 0

    def sequence_version_json(self):
        '''Returns a list of dictionaries describing reebill versions attached
        to this utility bill. Each element is of the form {"sequence":
        sequence, "version": version}. The elements are sorted by sequence and
        by version within the same sequence.
        '''
        return sorted(
            ({'sequence': ur.reebill.sequence, 'version': ur.reebill.version,
              'issue_date':ur.reebill.issue_date}
                 for ur in self._utilbill_reebills),
            key=lambda element: (element['sequence'], element['version'])
        )

    # TODO: this is no longer used; client receives JSON and renders it as a
    # string
    def sequence_version_string(self):
        '''Returns a string describing sequences and versions of reebills
        attached to this utility bill, consisting of sequences followed by a
        comma-separated list of versions of that sequence, e.g. "1-0,1,2, 2-0".
        '''
        # group _utilbill_reebills by sequence, sorted by version within each
        # group
        groups = groupby(sorted(self._utilbill_reebills,
                key=lambda x: (x.reebill.sequence, x.reebill.version)),
                key=attrgetter('reebill.sequence'))
        return ', '.join('%s-%s' % (sequence,
                ','.join(str(ur.reebill.version) for ur in group))
                for (sequence, group) in groups)

class Payment(Base):
    __tablename__ = 'payment'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    date_received = Column(DateTime, nullable=False)
    date_applied = Column(Date, nullable=False)
    description = Column(String)
    credit = Column(Float)

    customer = relationship("Customer", backref=backref('payments',
            order_by=id))

    '''date_received is the datetime when Skyline recorded the payment.
    date_applied is the date that the payment is "for", from the customer's
    perspective. Normally these are on the same day, but an error in an old
    payment can be corrected by entering a new payment with the same
    date_applied as the old one, whose credit is the true amount minus the
    previously-entered amount.'''
    def __init__(self, customer, date_received, date_applied, description,
            credit):
        assert isinstance(date_received, datetime)
        assert isinstance(date_applied, date)
        self.customer = customer
        self.date_received = date_received # datetime
        self.date_applied = date_applied   # date
        self.description = description
        self.credit = credit

    def to_dict(self):
        return {
            'id': self.id, 
            'date_received': self.date_received,
            'date_applied': self.date_applied,
            'description': self.description,
            'credit': self.credit,
            # the client uses this field to determine if users should be
            # allowed to edit this payment
            'editable': datetime.utcnow() - self.date_received \
                    < timedelta(hours=24)
        }

    def __repr__(self):
        return '<Payment(%s, received=%s, applied=%s, %s, %s)>' \
                % (self.customer.account, self.date_received, \
                        self.date_applied, self.description, self.credit)


# NOTE this is a view
class StatusDaysSince(Base):
    __tablename__ = 'status_days_since'

    # NOTE it seems that SQLAlchemy requires at least one column to be
    # identified as a "primary key" even though the table doesn't really have a
    # primary key in the db.
    account = Column(String, primary_key=True)
    dayssince = Column(Integer)

    def __init__(self, account, dayssince):
        self.account = account
        self.dayssince = dayssince

    def __repr__(self):
        return '<StatusDaysSince(%s, %s)>' \
                % (self.account, self.dayssince)


# TODO move the 2 functions below to Process? seems like state.py is only about
# the state database

def guess_utilbill_periods(start_date, end_date):
    '''Returns a list of (start, end) tuples representing a the number and
    periods of "hypothetical" utility bills covering the date range
    [start_date, end_date). "Hypothetical" utility bills are used for filling
    in a time gap between existing utility bills and a newly-uploaded one.'''
    if end_date <= start_date:
        raise ValueError('start date must precede end date.')

    # determine how many bills there are: divide total number of days by
    # hard-coded average period length of existing utilbills (computed using
    # utilbill_histogram.py), and round to nearest integer--but never go below
    # 1, since there must be at least 1 bill
    # TODO this hard-coded constant was the average period length of a sample
    # of many customers' utility bills; replace it with something smarter. we
    # should probably use a customer-specific average period length, since some
    # customers have 2-month utility bills.
    num_bills = max(1, int(round((end_date - start_date).days / 30.872)))

    # each bill's period will have the same length (except possibly the last
    # one)
    period_length = (end_date - start_date).days / num_bills

    # generate periods: all periods except the last have length
    # 'period_length'; last period may be slightly longer to fill up any
    # remaining space
    periods = []
    for i in range(num_bills-1):
        periods.append((start_date + timedelta(days= i * period_length),
                start_date + timedelta(days= (i + 1) * period_length)))
    periods.append((start_date + timedelta(days= (num_bills-1) * period_length),
        end_date))
    return periods


class StateDB(object):

    config = None

    def __init__(self, host, database, user, password, db_connections=5, logger=None):
        # put "echo=True" in the call to create_engine to print the SQL
        # statements that are executed
        engine = create_engine('mysql://%s:%s@%s:3306/%s' % (user, password,
                host, database), pool_recycle=3600, pool_size=db_connections)

        # To turn logging on
        import logging
        logging.basicConfig()
        #logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
        #logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)

        # global variable for the database session: SQLAlchemy will give an
        # error if this is created more than once, so don't call _getSession()
        # anywhere else wrapped by scoped_session for thread contextualization
        # http://docs.sqlalchemy.org/en/latest/orm/session.html#unitofwork-contextual
        self.session = scoped_session(sessionmaker(bind=engine,
                autoflush=True))

        # TODO don't default to None
        self.logger = logger

    def get_customer(self, session, account):
        return session.query(Customer).filter(Customer.account==account).one()

    def get_next_account_number(self, session):
        '''Returns what would become the next account number if a new account
        were created were created (highest existing account number + 1--we're
        assuming accounts will be integers, even though we always store them as
        strings).'''
        last_account = max(map(int, self.listAccounts(session)))
        return last_account + 1

    def get_utilbill(self, session, account, service, start, end):
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        return session.query(UtilBill)\
                .filter(UtilBill.customer_id==customer.id)\
                .filter(UtilBill.service==service)\
                .filter(UtilBill.period_start==start)\
                .filter(UtilBill.period_end==end).one()

    def get_utilbill_by_id(self, session, ubid):
        return session.query(UtilBill).filter(UtilBill.id==ubid).one()

    def utilbills_for_reebill(self, session, account, sequence, version='max'):
        '''Returns all utility bills for the reebill given by account,
        sequence, version (highest version by default).'''
        reebill = self.get_reebill(session, account, sequence, version=version)
        utilbills = session.query(UtilBill)\
                .filter(UtilBill.reebills.contains(reebill))\
                .order_by(UtilBill.period_start)
        return utilbills.all()

    #def delete_reebill(self, session, reebill):
        #'''Deletes the highest version of the given reebill, if it's not
        #issued.'''
        ## note that reebills whose version is below the maximum version should
        ## always be issued
        #if self.is_issued(session, account, sequence):
            #raise IssuedBillError("Can't delete an issued reebill")

        ## utility bill association is removed automatically because of "on
        ## delete cascade" setting on foreign key constraint of the
        ## utilbill_reebill table
        #session.delete(reebill)

    def max_version(self, session, account, sequence):
        # surprisingly, it is possible to filter a ReeBill query by a Customer
        # column even without actually joining with Customer. because of
        # func.max, the result is a tuple rather than a ReeBill object.
        reebills_subquery = session.query(ReeBill).join(Customer)\
                .filter(ReeBill.customer_id==Customer.id)\
                .filter(Customer.account==account)\
                .filter(ReeBill.sequence==sequence)
        max_version = session.query(func.max(
                reebills_subquery.subquery().columns.version)).one()[0]
        # SQLAlchemy returns None when the reebill row doesn't exist, but that
        # should be reported as an exception
        if max_version == None:
            raise NoResultFound
            
        # SQLAlchemy returns a "long" here for some reason, so convert to int
        return int(max_version)

    def max_issued_version(self, session, account, sequence):
        '''Returns the greatest version of the given reebill that has been
        issued. (This should differ by at most 1 from the maximum version
        overall, since a new version can't be created if the last one hasn't
        been issued.) If no version has ever been issued, returns None.'''
        # weird filtering on other table without a join
        customer = self.get_customer(session, account)
        result = session.query(func.max(ReeBill.version))\
                .filter(ReeBill.customer == customer)\
                .filter(ReeBill.issued==1).one()[0]
        # SQLAlchemy returns None if no reebills with that customer are issued
        if result is None:
            return None
        # version number is a long, so convert to int
        return int(result)

    # TODO rename to something like "create_next_version"
    def increment_version(self, session, account, sequence):
        '''Creates a new reebill with version number 1 greater than the highest
        existing version for the given account and sequence.
        
        The utility bill(s) of the new version are the same as those of its
        predecessor, but utility bill, UPRS, and document_ids are cleared
        from the utilbill_reebill table, meaning that the new reebill's
        utilbill/UPRS documents are the current ones.
        
        Returns the new state.ReeBill object.'''
        # highest existing version must be issued
        current_max_version_reebill = self.get_reebill(session, account,
                sequence)
        if current_max_version_reebill.issued != 1:
            raise ValueError(("Can't increment version of reebill %s-%s "
                    "because version %s is not issued yet") % (account,
                    sequence, max_version))

        new_reebill = ReeBill(current_max_version_reebill.customer, sequence,
                current_max_version_reebill.version + 1,
                discount_rate=current_max_version_reebill.discount_rate,
                late_charge_rate=current_max_version_reebill.late_charge_rate,
                utilbills=current_max_version_reebill.utilbills)
        for ur in new_reebill._utilbill_reebills:
            ur.document_id, ur.uprs_id, = None, None

        session.add(new_reebill)
        return new_reebill

    def get_unissued_corrections(self, session, account):
        '''Returns a list of (sequence, version) pairs for bills that have
        versions > 0 that have not been issued.'''
        reebills = session.query(ReeBill).join(Customer)\
                .filter(Customer.account==account)\
                .filter(ReeBill.version > 0)\
                .filter(ReeBill.issued==0).all()
        return [(int(reebill.sequence), int(reebill.version)) for reebill
                in reebills]

    def discount_rate(self, session, account):
        '''Returns the discount rate for the customer given by account.'''
        result = session.query(Customer).filter_by(account=account).one().\
                get_discount_rate()
        return result
        
    def late_charge_rate(self, session, account):
        '''Returns the late charge rate for the customer given by account.'''
        result = session.query(Customer).filter_by(account=account).one()\
                .get_late_charge_rate()
        return result

    # TODO: 22598787 branches
    def last_sequence(self, session, account):
        '''Returns the sequence of the last reebill for 'account', or 0 if
        there are no reebills.'''
        customer = self.get_customer(session, account)
        max_sequence = session.query(sqlalchemy.func.max(ReeBill.sequence)) \
                .filter(ReeBill.customer_id==customer.id).one()[0]
        # TODO: because of the way 0.xml templates are made (they are not in
        # the database) reebill needs to be primed otherwise the last sequence
        # for a new bill is None. Design a solution to this issue.
        if max_sequence is None:
            max_sequence =  0
        return max_sequence
        
    def last_issued_sequence(self, session, account,
            include_corrections=False):
        '''Returns the sequence of the last issued reebill for 'account', or 0
        if there are no issued reebills.'''
        customer = self.get_customer(session, account)
        if include_corrections:
            filter_logic = sqlalchemy.or_(ReeBill.issued==1,
                    sqlalchemy.and_(ReeBill.issued==0, ReeBill.version>0))
        else:
            filter_logic = ReeBill.issued==1

        max_sequence = session.query(sqlalchemy.func.max(ReeBill.sequence)) \
                .filter(ReeBill.customer_id==customer.id) \
                .filter(filter_logic).one()[0]
        if max_sequence is None:
            max_sequence = 0
        return max_sequence

    def get_last_reebill(self, session, account, issued_only=False):
        '''Returns the highest-sequence, highest-version ReeBill object for the
        given account, or None if no reebills exist. if issued_only is True,
        returns the highest-sequence/version issued reebill.
        '''
        customer = self.get_customer(session, account)
        cursor = session.query(ReeBill).filter_by(customer=customer)\
                .order_by(desc(ReeBill.sequence), desc(ReeBill.version))
        if issued_only:
            cursor = cursor.filter_by(issued=True)
        if cursor.count() == 0:
            return None
        return cursor.first()

    def get_last_utilbill(self, session, account, service=None, utility=None,
            rate_class=None, end=None):
        '''Returns the latest (i.e. last-ending) utility bill for the given
        account matching the given criteria. If 'end' is given, the last
        utility bill ending before or on 'end' is returned.'''
        cursor = session.query(UtilBill).join(Customer)\
                .filter(UtilBill.customer_id == Customer.id)\
                .filter(Customer.account == account)
        if service is not None:
            cursor = cursor.filter(UtilBill.service == service)
        if utility is not None:
            cursor = cursor.filter(UtilBill.utility == utility)
        if rate_class is not None:
            cursor = cursor.filter(UtilBill.rate_class == rate_class)
        if end is not None:
            cursor = cursor.filter(UtilBill.period_end <= end)
        result = cursor.order_by(UtilBill.period_end).first()
        if result is None:
            raise NoSuchBillException("No utility bill found")
        return result

    def last_utilbill_end_date(self, session, account):
        '''Returns the end date of the latest utilbill for the customer given
        by 'account', or None if there are no utilbills.'''
        customer = self.get_customer(session, account)
        query_results = session.query(sqlalchemy.func.max(UtilBill.period_end))\
                .filter(UtilBill.customer_id==customer.id).one()
        if len(query_results) > 0:
            return query_results[0]
        return None

    def new_reebill(self, session, account, sequence, version=0):
        '''Creates a new reebill row in the database and returns the new
        ReeBill object corresponding to it.'''
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        new_reebill = ReeBill(customer, sequence, version)
        session.add(new_reebill)
        return new_reebill

    def issue(self, session, account, sequence, issue_date=datetime.utcnow()):
        '''Marks the highest version of the reebill given by account, sequence
        as issued.
        '''
        reebill = self.get_reebill(session, account, sequence)
        if reebill.issued == 1:
            raise IssuedBillError(("Can't issue reebill %s-%s-%s because it's "
                    "already issued") % (account, sequence, reebill.version))
        reebill.issued = 1
        reebill.issue_date = issue_date

    def is_issued(self, session, account, sequence, version='max',
            nonexistent=None):
        '''Returns true if the reebill given by account, sequence, and version
        (latest version by default) has been issued, false otherwise. If
        'nonexistent' is given, that value will be returned if the reebill is
        not present in the state database (e.g. False when you want
        non-existent bills to be treated as unissued).'''
        # NOTE: with the old database schema (one reebill row for all versions)
        # this method returned False when the 'version' argument was higher
        # than max_version. that was probably the wrong behavior, even though
        # test_state:StateTest.test_versions tested for it. 
        try:
            if version == 'max':
                reebill = self.get_reebill(session, account, sequence)
            elif isinstance(version, int):
                reebill = self.get_reebill(session, account, sequence, version)
            else:
                raise ValueError('Unknown version specifier "%s"' % version)
            # NOTE: reebill.issued is an int, and it converts the entire
            # expression to an int unless explicitly cast! see
            # https://www.pivotaltracker.com/story/show/35965271
            return bool(reebill.issued == 1)
        except NoResultFound:
            if nonexistent is not None:
                return nonexistent
            raise

    def account_exists(self, session, account):
        try:
           customer = session.query(Customer).with_lockmode("read")\
                   .filter(Customer.account==account).one()
        except NoResultFound:
            return False

        return True

    def listAccounts(self, session):
        '''List of all customer accounts (ordered).'''    
        # SQLAlchemy returns a list of tuples, so convert it into a plain list
        result = map((lambda x: x[0]),
                session.query(Customer.account)\
                .order_by(Customer.account).all())
        return result

    def list_accounts(self, session, start, limit):
        '''List of customer accounts with start and limit (for paging).'''
        # SQLAlchemy returns a list of tuples, so convert it into a plain list
        query = session.query(Customer.account)
        slice = query[start:start + limit]
        count = query.count()
        result = map((lambda x: x[0]), slice)
        return result, count

    def listSequences(self, session, account):

        # TODO: figure out how to do this all in one query. many SQLAlchemy
        # subquery examples use multiple queries but that shouldn't be
        # necessary
        customer = session.query(Customer).filter(Customer.account==account).one()
        sequences = session.query(ReeBill.sequence).with_lockmode("read") \
                .filter(ReeBill.customer_id==customer.id).all()

        # sequences is a list of tuples of numbers, so convert it into a plain list
        result = map((lambda x: x[0]), sequences)

        return result

    def listReebills(self, session, start, limit, account, sort, dir, **kwargs):
        query = session.query(ReeBill).join(Customer)\
                .filter(Customer.account==account)
        
        if (dir == u'DESC'):
            order = desc
        elif (dir == u'ASC'):
            order = asc
        else:
            raise ValueError("Bad Parameter Value: 'dir' must be 'ASC' or 'DESC'")

        if (sort == u'sequence'):
            field = ReeBill.sequence
        else:
            raise ValueError("Bad Parameter Value: 'sort' must be 'sequence'")

        slice = query.order_by(order(field))[start:start + limit]
        count = query.count()

        return slice, count

    def reebills(self, session, include_unissued=True):
        '''Generates (account, sequence, max version) tuples for all reebills
        in MySQL.'''
        for account in self.listAccounts(session):
            for sequence in self.listSequences(session, account):
                reebill = self.get_reebill(session, account, sequence)
                if include_unissued or reebill.issued:
                    yield account, int(sequence), int(reebill.max_version)

    def reebill_versions(self, session, include_unissued=True):
        '''Generates (account, sequence, version) tuples for all reebills in
        MySQL.'''
        for account in self.listAccounts(session):
            for sequence in self.listSequences(session, account):
                reebill = self.get_reebill(session, account, sequence)
                if include_unissued or reebill.issued:
                    max_version = reebill.max_version
                else:
                    max_version = reebill.max_version - 1
                for version in range(max_version + 1):
                    yield account, sequence, version

    def get_reebill(self, session, account, sequence, version='max'):
        '''Returns the ReeBill object corresponding to the given account,
        sequence, and version (the highest version if no version number is
        given).'''
        if version == 'max':
            version = session.query(func.max(ReeBill.version)).join(Customer) \
                .filter(Customer.account==account) \
                .filter(ReeBill.sequence==sequence).one()[0]
        result = session.query(ReeBill).join(Customer) \
            .filter(Customer.account==account) \
            .filter(ReeBill.sequence==sequence)\
            .filter(ReeBill.version==version).one()
        return result

    def get_reebill_by_id(self, session, rbid):
        return session.query(ReeBill).filter(ReeBill.id==rbid).one()

    def get_descendent_reebills(self, session, account, sequence):

        query = session.query(ReeBill).join(Customer) \
            .filter(Customer.account==account) \
            .order_by(ReeBill.sequence)

        slice = query[int(sequence):]

        return slice

    def list_utilbills(self, session, account, start=None, limit=None):
        '''Queries the database for account, start date, and end date of bills
        in a slice of the utilbills table; returns the slice and the total
        number of rows in the table (for paging). If 'start' is not given, all
        bills are returned. If 'start' is given but 'limit' is not, all bills
        starting with index 'start'. If both 'start' and 'limit' are given,
        returns bills with indices in [start, start + limit).'''

        # SQLAlchemy query to get account & dates for all utilbills
        query = session.query(UtilBill).with_lockmode('read').join(Customer)\
                .filter(Customer.account==account)\
                .order_by(Customer.account, desc(UtilBill.period_start))

        if start is None:
            return query, query.count()
        if limit is None:
            return query[start:], query.count()
        # SQLAlchemy does SQL 'limit' with Python list slicing
        return query[start:start + limit], query.count()

    def get_utilbills_on_date(self, session, account, the_date):
        '''Returns a list of UtilBill objects representing MySQL utility bills
        whose periods start before/on and end after/on 'the_date'.'''
        return session.query(UtilBill).filter(
            UtilBill.customer==self.get_customer(session, account),
            UtilBill.period_start<=the_date,
            UtilBill.period_end>the_date).all()

    
    def fill_in_hypothetical_utilbills(self, session, account, service,
            utility, rate_class, begin_date, end_date):
        '''Creates hypothetical utility bills in MySQL covering the period
        [begin_date, end_date).'''
        # get customer id from account number
        customer = session.query(Customer).filter(Customer.account==account) \
                .one()

        for (start, end) in guess_utilbill_periods(begin_date, end_date):
            # make a UtilBill
            # note that all 3 Mongo documents are None
            utilbill = UtilBill(customer, UtilBill.Hypothetical, service,
                    utility, rate_class, period_start=start, period_end=end)
            # put it in the database
            session.add(utilbill)

    def trim_hypothetical_utilbills(self, session, account, service):
        '''Deletes hypothetical utility bills for the given account and service
        whose periods precede the start date of the earliest non-hypothetical
        utility bill or follow the end date of the last utility bill.'''
        customer = self.get_customer(session, account)
        all_utilbills = session.query(UtilBill)\
                .filter(UtilBill.customer == customer)
        real_utilbills = all_utilbills\
                .filter(UtilBill.state != UtilBill.Hypothetical)
        hypothetical_utilbills = all_utilbills\
                .filter(UtilBill.state == UtilBill.Hypothetical)

        # if there are no real utility bills, delete all the hypothetical ones
        # (i.e. all of the utility bills for this customer)
        if real_utilbills.count() == 0:
            for hb in hypothetical_utilbills:
                session.delete(hb)
            return

        # if there are real utility bills, only delete the hypothetical ones
        # whose entire period comes before end of first real bill or after
        # start of last real bill
        first_real_utilbill = real_utilbills\
                .order_by(asc(UtilBill.period_start))[0]
        last_real_utilbill = session.query(UtilBill)\
                .order_by(desc(UtilBill.period_start))[0]
        for hb in hypothetical_utilbills:
            if (hb.period_start <= first_real_utilbill.period_end \
                    and hb.period_end <= first_real_utilbill.period_end)\
                    or (hb.period_end >= last_real_utilbill.period_start\
                    and hb.period_start >= last_real_utilbill.period_start):
                session.delete(hb)

    def get_last_real_utilbill(self, session, account, end, service=None,
            utility=None, rate_class=None, processed=None):
        '''Returns the latest-ending non-Hypothetical UtilBill whose
        end date is before/on 'end', optionally with the given service,
        utility, rate class, and 'processed' status.
        '''
        customer = self.get_customer(session, account)
        cursor = session.query(UtilBill)\
                .filter(UtilBill.customer == customer)\
                .filter(UtilBill.state != UtilBill.Hypothetical)\
                .filter(UtilBill.period_end <= end)
        if service is not None:
            cursor = cursor.filter(UtilBill.service == service)
        if utility is not None:
            cursor = cursor.filter(UtilBill.utility == utility)
        if rate_class is not None:
            cursor = cursor.filter(UtilBill.rate_class == rate_class)
        if processed is not None:
            assert isinstance(processed, bool)
            cursor = cursor.filter(UtilBill.processed == processed)
        result = cursor.order_by(desc(UtilBill.period_end)).first()
        if result is None:
            raise NoSuchBillException
        return result

    def create_payment(self, session, account, date_applied, description,
            credit, date_received=None):
        '''Adds a new payment, returns the new Payment object. By default,
        'date_received' is the current datetime in UTC when this method is
        called; only override this for testing purposes.'''
        # NOTE a default value for 'date_received' can't be specified as a
        # default argument in the method signature because it would only get
        # evaluated once at the time this module was imported, which means its
        # value would be the same every time this method is called.
        if date_received is None:
            date_received = datetime.utcnow()
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        new_payment = Payment(customer, date_received, date_applied,
                description, credit)
        session.add(new_payment)
        return new_payment

    def update_payment(self, session, oid, date_applied, description, credit):
        '''Sets the date_applied, description, and credit of the payment with
        id 'oid'.'''
        payment = session.query(Payment).filter(Payment.id == oid).one()
        if isinstance(date_applied, basestring):
            payment.date_applied = datetime.strptime(date_applied,
                    "%Y-%m-%dT%H:%M:%S").date()
        else:
            payment.date_applied = date_applied
        payment.description = description
        payment.credit = credit

    def delete_payment(self, session, oid):
        '''Deletes the payment with id 'oid'.'''
        payment = session.query(Payment).filter(Payment.id == oid).one()
        session.delete(payment)

    def find_payment(self, session, account, periodbegin, periodend):
        '''Returns a list of payment objects whose date_applied is in
        [periodbegin, period_end).'''
        # periodbegin and periodend must be non-overlapping between bills. This
        # is in direct opposition to the reebill period concept, which is a
        # period that covers all services for a given reebill and thus overlap
        # between bills.  Therefore, a non overlapping period could be just the
        # first utility service on the reebill. If the periods overlap,
        # payments will be applied more than once. See 11093293
        payments = session.query(Payment)\
            .filter(Payment.customer_id == Customer.id) \
            .filter(Customer.account == account) \
            .filter(and_(Payment.date_applied >= periodbegin,
            Payment.date_applied < periodend)).all()
        return payments
        
    def get_total_payment_since(self, session, account, start,
            end=datetime.utcnow().date()):
        '''Returns sum of all account's payments applied on or after 'start'
        and before 'end' (today by default). If 'start' is None, the beginning
        of the interval extends to the beginning of time.
        '''
        assert type(start), type(end) == (date, date)
        payments = session.query(Payment)\
                .filter(Payment.customer==self.get_customer(session, account))\
                .filter(Payment.date_applied < end)
        if start is not None:
            payments = payments.filter(Payment.date_applied >= start)
        return float(sum(payment.credit for payment in payments.all()))

    def payments(self, session, account):
        '''Returns list of all payments for the given account ordered by
        date_received.'''
        payments = session.query(Payment).join(Customer)\
            .filter(Customer.account==account).order_by(Payment.date_received).all()
        return payments

    def retrieve_status_days_since(self, session, sort_col, sort_order):
        # SQLAlchemy query to get account & dates for all utilbills
        entityQuery = session.query(StatusDaysSince)

        # example of how db sorting would be done
        #if sort_col == 'dayssince' and sort_order == 'ASC':
        #    sortedQuery = entityQuery.order_by(asc(StatusDaysSince.dayssince))
        #elif sort_colr == 'dayssince' and sort_order == 'DESC':
        #    sortedQuery = entityQuery.order_by(desc(StatusDaysSince.dayssince))
        #lockmodeQuery = sortedQuery.with_lockmode("read")

        lockmodeQuery = entityQuery.with_lockmode("read")

        result = lockmodeQuery.all()

        return result

class UtilBillLoader(object):
    '''Data access object for utility bills, used to hide database details
    from other classes so they can be more easily tested.
    '''
    def __init__(self, session):
        ''''session': SQLAlchemy session object to be used for database
        queries.
        '''
        self._session = session

    def load_real_utilbills(self, **kwargs):
        '''Returns a cursor of UtilBill objects matching the criteria given
        by **kwargs. Only "real" utility bills (i.e. UtilBill objects with
        state SkylineEstimated or lower) are included.
        '''
        cursor = self._session.query(UtilBill).filter(UtilBill.state <=
                UtilBill.SkylineEstimated)
        for key, value in kwargs.iteritems():
            cursor = cursor.filter(getattr(UtilBill, key) == value)
        return cursor

if __name__ == '__main__':
    # verify that SQLAlchemy setup is working
    s = StateDB(host='localhost', database='skyline_dev', user='dev',
            password='dev')
    session = s.session()
    print session.query(Customer).count(), 'customers found'
    
    ub = session.query(UtilBill).first()
    rb = session.query(ReeBill).first()
    print rb.utilbills
    print rb.document_id_for_utilbill(ub)

    customer = session.query(Customer).first()

    c = session.query(Customer).first()
    r = ReeBill(c, 100, version=0, utilbills=[])
    u = UtilBill(c, UtilBill.Complete, 'gas', 'washgas', 'NONRES HEAT',
            period_start=date(2013,1,1), period_end=date(2013,2,1))
    print u._utilbill_reebills, r._utilbill_reebills, r.utilbills, u.is_attached()
    ur = UtilbillReebill(u)
    u._utilbill_reebills.append(ur)
    print u._utilbill_reebills, r._utilbill_reebills, r.utilbills, u.is_attached()

