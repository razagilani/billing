#!/usr/bin/python
"""
Utility functions to interact with state database
"""
import os, sys
import itertools
import datetime
import operator
from datetime import timedelta, datetime, date
from decimal import Decimal
import sqlalchemy
from sqlalchemy import Table, Integer, String, Float, MetaData, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import mapper, sessionmaker, scoped_session
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import and_
from sqlalchemy.sql.expression import desc, asc, label
from sqlalchemy.sql.functions import max as sql_max
from sqlalchemy.sql.functions import min as sql_min
from sqlalchemy import func, not_
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from billing.processing.exceptions import BillStateError, IssuedBillError, NoSuchBillException
sys.stdout = sys.stderr

# Python's datetime.min is too early for the MySQLdb module; including it in a
# query to mean "the beginning of time" causes a strptime failure, so this
# value should be used instead.
MYSQLDB_DATETIME_MIN = datetime(1900,1,1)


# this base class should be extended by all objects representing SQLAlchemy
# tables
Base = declarative_base()

# SQLAlchemy table object to be used in creating the association between the
# UtilBill and ReeBill classes below
utilbill_reebill_table = Table('utilbill_reebill', Base.metadata,
        Column('utilbill_id', Integer, ForeignKey('utilbill.id')),
        Column('reebill_id', Integer, ForeignKey('reebill.id')),
        Column('document_id', String)
)

class Customer(Base):
    __tablename__ = 'customer'

    id = Column(Integer, primary_key=True)
    account = Column(String, nullable=False)
    name = Column(String)
    discountrate = Column(Float, nullable=False)
    latechargerate = Column(Float, nullable=False)

    def __init__(self, name, account, discount_rate, late_charge_rate,
            utilbill_template_id):
        self.name = name
        self.account = account
        self.discountrate = discount_rate
        self.latechargerate = late_charge_rate
        self.utilbill_template_id = utilbill_template_id

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

    customer = relationship("Customer", backref=backref('reebills',
            order_by=id))

    def __init__(self, customer, sequence, version=0):
        self.customer = customer
        self.sequence = sequence
        self.issued = 0
        self.version = version

    def __repr__(self):
        return '<ReeBill(account=%s, sequence=%s, max_version=%s, issued=%s)>' \
                % (self.customer, self.sequence, self.max_version, self.issued)

class UtilBill(Base):
    __tablename__ = 'utilbill'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    state = Column(Integer, nullable=False)
    service = Column(String, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    total_charges = Column(Float)
    date_received = Column(Date)
    processed = Column(Integer, nullable=False)
    document_id = Column(String)
    cprs_document_id = Column(String)
    uprs_document_id = Column(String)

    customer = relationship("Customer", backref=backref('utilbills',
            order_by=id))
    reebills = relationship('ReeBill', backref='utilbills',
            secondary=utilbill_reebill_table)

    # utility bill states:
    # 0. Complete: actual non-estimated utility bill.
    # 1. Utility estimated: actual utility bill whose contents were estimated by
    # the utility (and which will be corrected later to become Complete).
    # 2. Skyline estimated: a bill that is known to exist (and whose dates are
    # correct) but whose contents were estimated by Skyline.
    # 3. Hypothetical: Skyline supposes that there is probably a bill during a
    # certain time period and estimates what its contents would be if it existed.
    # Such a bill may not really exist (since we can't even know how many bills
    # there are in a given period of time), and if it does exist, its actual dates
    # will probably be different than the guessed ones.
    # TODO 38385969: not sure this strategy is a good idea
    Complete, UtilityEstimated, SkylineEstimated, Hypothetical = range(4)

    def __init__(self, customer, state, service, period_start=None,
            period_end=None, total_charges=0, date_received=None,
            processed=False, reebill=None):
        '''State should be one of UtilBill.Complete, UtilBill.UtilityEstimated,
        UtilBill.SkylineEstimated, UtilBill.Hypothetical.'''
        # utility bill objects also have an 'id' property that SQLAlchemy
        # automatically adds from the database column
        self.customer = customer
        self.state = state
        self.service = service
        self.period_start = period_start
        self.period_end = period_end
        self.total_charges = total_charges
        self.date_received = date_received
        self.processed = processed
        self.reebill = reebill # newly-created utilbill has NULL in reebill_id column

    @property
    def has_reebill(self):
        return self.reebill != None

    def __repr__(self):
        return '<UtilBill(customer=%s, service=%s, period_start=%s, period_end=%s)>' \
                % (self.customer, self.service, self.period_start, self.period_end)

#class UtilBillReeBill(object):
    #'''Class corresponding to the "utilbill_reebill" table which represents the
    #many-to-many relationship between "utilbill" and "reebill".'''
    #def __init__(self, utilbill_id, reebill_id, document_id=None):
        #self.utilbill_id = utilbill_id
        #self.reebill_id = reebill_id
        #self.document_id = document_id

    #def __repr__(self):
        #return 'UtilBillReeBill(utilbill_id=%s, reebill_id=%s, document_id=%s)' % (
                #self.utilbill_id, self.reebill_id, self.document_id)

class Payment(Base):
    __tablename__ = 'payment'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    date_received = Column(Date, nullable=False)
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
            'editable': datetime.utcnow() - self.date_received < timedelta(hours=24)
        }

    def __repr__(self):
        return '<Payment(%s, %s, %s, %s, %s)>' \
                % (self.customer, self.date_received, \
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

    # each bill's period will have the same length (except possibly the last one)
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

#def guess_utilbills_and_end_date(session, account, start_date):
#    '''Returns a tuple (end_date, [utilbills]): a list of utility bills that
#    will probably be associated with a newly-created reebill for the customer
#    given by 'account' starting on 'start_date', and a guess for the reebills'
#    end date.'''
#    # TODO:25731853 test this method with multi-service customers. it works very well
#    # for customers with one utility service, but the more utility bills the
#    # customer has, the less accurate it will be.
#
#    # Rich added this because of bug 26512637, which is really a data problem
#    # (reebill period dates are missing)
#    # TODO remove this because it's a temporary workaround
#    if start_date == None:
#        print >> sys.stderr, 'guess_utilbills_and_end_date got start_date == None'
#        return (None, []) 
#
#    # get length of last reebill (note that we don't store dates for reebills
#    # in MySQL)
#    customer = session.query(Customer).filter(Customer.account==account).one()
#    previous_reebills = session.query(ReeBill) \
#            .filter(ReeBill.customer_id==customer.id) \
#            .order_by(desc(ReeBill.sequence))
#    try:
#        # get last reebill. note that SQLALchemy cursor object has no len (you
##        # have to issue another query with func.count)
#        last_reebill = previous_reebills[0]
#    except IndexError:
#        # if there are no previous bills, guess 30 days
#        # TODO make this guess better?
#        length = timedelta(days=30)
#    else:
#        # otherwise, get length of last bill period
#        last_reebill_utilbills = session.query(UtilBill) \
#                .filter(UtilBill.reebill_id==last_reebill.id)
#        if list(last_reebill_utilbills) == []:
#            raise Exception("Can't determine new reebill period without "
#                    + "utility bills attached to the last reebill")
#        earliest_start = min(ub.period_start for ub in last_reebill_utilbills)
#        latest_end = max(ub.period_end for ub in last_reebill_utilbills)
#        length = (latest_end - earliest_start)
#
#    # first guess that this reebill's period has the same length as the last.
#    # this guess will be adjusted to match the closest utility bill end date
#    # after 'start_date', if there are any such utility bills.
#    probable_end_date = start_date + length
#
#    # get all utility bills that end after start_date
#    utilbills_after_start_date = session.query(UtilBill) \
#            .filter(UtilBill.customer_id==customer.id) \
#            .filter(UtilBill.period_end > start_date).all()
#
#    # if there are no utility bills that might be associated with this reebill,
#    # we can't guess very well--just assume that this reebill's period will be
#    # exactly the same length as its predecessor's.
#    if len(utilbills_after_start_date) == 0:
#        return probable_end_date, []
#
#    # otherwise, adjust the guess to the closest utility bill end date (either
#    # forward or back); return that date and all utilbills that end in the date
#    # interval (start_date, probable_end_date].
#    probable_end_date = min([u.period_end for u in utilbills_after_start_date],
#            key = lambda x: abs(probable_end_date - x))
#    return probable_end_date, [u for u in utilbills_after_start_date if
#            u.period_end <= probable_end_date]

class StateDB(object):

    config = None

    def __init__(self, host, database, user, password, db_connections=5):
        # put "echo=True" in the call to create_engine to print the SQL
        # statements that are executed
        engine = create_engine('mysql://%s:%s@%s:3306/%s' % (user, password,
                host, database), pool_recycle=3600, pool_size=db_connections)

        # To turn logging on
        import logging
        logging.basicConfig()
        #logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
        #logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)

        # global variable for the database session: SQLAlchemy will give an error if
        # this is created more than once, so don't call _getSession() anywhere else
        # wrapped by scoped_session for thread contextualization
        # http://docs.sqlalchemy.org/en/latest/orm/session.html#unitofwork-contextual
        self.session = scoped_session(sessionmaker(bind=engine,
                autoflush=True))

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

    def try_to_attach_utilbills(self, session, account, sequence, utilbills,
            suspended_services=[]):
        '''Raises an exception if 'attach_utilbills' would fail, does not
        modify any databases.'''
        if not utilbills:
            # TODO this error message sucks
            raise BillStateError('No utility bills passed')
        non_suspended_utilbills = [u for u in utilbills if u.service.lower() not in suspended_services]
        if not non_suspended_utilbills:
            raise BillStateError('No utility bills to attach because the %s services '
                    ' are suspended' % ', '.join(suspended_services))

    # TODO move to process.py?
    def attach_utilbills(self, session, account, sequence, utilbills, suspended_services=[]):
        '''Records in MySQL the association between the reebill given by
        'account', 'sequence' and all utilbills belonging to that customer
        whose entire periods are within the date interval [start, end] and
        whose services are not in 'suspended_services'. The utility bills are
        marked as processed.'''
        if not utilbills:
            raise BillStateError('No utility bills passed')

        non_suspended_utilbills = [u for u in utilbills if u.service.lower() not in suspended_services]
        if not non_suspended_utilbills:
            raise BillStateError('No utility bills to attach because the %s services'\
                    ' are suspended' % ', '.join(suspended_services))
        
        reebill = self.get_reebill(session, account, sequence)

        for utilbill in utilbills:
            utilbill.reebills.append(reebill)
            utilbill.processed = True

    # TODO this will become obsolete now that reebills can't exist without
    # being attached
    def is_attached(self, session, account, sequence, nonexistent=None):
        '''Returns True iff the the highest version of the reebill given by
        account, sequence has utility bills attached to it in MySQL. If
        'nonexistent' is given, that value will be returned if the reebill is
        not present in the state database (e.g. False when you want
        non-existent bills to be treated as unissued).'''
        try:
            reebill = self.get_reebill(session, account, sequence,
                    version='max')
            num_utilbills = session.query(UtilBill)\
                    .filter(UtilBill.reebills.contains(reebill)).count()
        except NoResultFound:
            if nonexistent is not None:
                return nonexistent
            raise
        return num_utilbills >= 1

    def utilbills_for_reebill(self, session, account, sequence, version='max'):
        '''Returns all utility bills for the reebill given by account,
        sequence, version (highest version by default).'''
        reebill = self.get_reebill(session, account, sequence, version=version)
        utilbills = session.query(UtilBill)\
                .filter(UtilBill.reebills.contains(reebill))\
                .order_by(UtilBill.period_start)
        return utilbills.all()

    def delete_reebill(self, session, account, sequence):
        '''Deletes the highest version of the given reebill, if it's not
        issued.'''
        # note that reebills whose version is below the maximum version should
        # always be issued
        if self.is_issued(session, account, sequence):
            raise IssuedBillError("Can't delete an issued reebill")

        reebill = self.get_reebill(session, account, sequence)

        # utility bill association is removed automatically because of "on
        # delete cascade" setting on foreign key constraint of the
        # utilbill_reebill table
        session.delete(reebill)

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
        result = session.query(func.max(ReeBill.version))\
                .filter(Customer.account==account)\
                .filter(ReeBill.issued==1).one()[0]
        # SQLAlchemy returns None if no reebills with that customer are issued
        if result is None:
            return None
        # version number is a long, so convert to int
        return int(result)

    # TODO rename to something like "create_next_version"
    def increment_version(self, session, account, sequence):
        '''Creates a new reebill with version number 1 greater than the highest
        existing version for the given account and sequence. The utility
        bill(s) of the new version are the same as those of its predecessor.'''
        # highest existing version must be issued
        current_max_version_reebill = self.get_reebill(session, account,
                sequence)
        if current_max_version_reebill.issued != 1:
            raise ValueError(("Can't increment version of reebill %s-%s "
                    "because version %s is not issued yet") % (account,
                    sequence, max_version))
        session.add(ReeBill(current_max_version_reebill.customer, sequence,
                current_max_version_reebill.version + 1,
                utilbills=current_max_version_reebill.utilbills))

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
                discountrate
        return result
        
    def late_charge_rate(self, session, account):
        '''Returns the late charge rate for the customer given by account.'''
        result = session.query(Customer).filter_by(account=account).one()\
                .latechargerate
        return result

    # TODO: 22598787 branches
    def last_sequence(self, session, account):
        '''Returns the sequence of the last reebill for 'account', or 0 if
        there are no reebills.'''
        customer = session.query(Customer).filter(Customer.account==account).one()
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
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
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
        customer = session.query(Customer).filter(Customer.account==account).one()
        query_results = session.query(sqlalchemy.func.max(UtilBill.period_end)) \
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

    def issue(self, session, account, sequence):
        '''Marks the highest version of the reebill given by account, sequence
        as issued. Does not set the issue date or due date, since those are
        stored in Mongo).'''
        reebill = self.get_reebill(session, account, sequence)
        if reebill.issued == 1:
            raise IssuedBillError(("Can't issue reebill %s-%s-%s because it's "
                    "already issued") % (account, sequence, reebill.version))
        reebill.issued = 1

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
           customer = session.query(Customer).with_lockmode("read").filter(Customer.account==account).one()
        except NoResultFound:
            return False

        return True

    def listAccounts(self, session):
        '''List of all customer accounts (ordered).'''    
        # SQLAlchemy returns a list of tuples, so convert it into a plain list
        result = map((lambda x: x[0]),
                session.query(Customer.account).order_by(Customer.account).all())
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

        query = session.query(ReeBill).join(Customer).filter(Customer.account==account)
        
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

    def listAllIssuableReebillInfo(self, session):
        '''Returns a list containing the account, sequence, and total utility
        bill charges (from MySQL) of the earliest unissued version-0 reebill
        each account, and the size of the list.'''
        unissued_v0_reebills = session.query(ReeBill.sequence, ReeBill.customer_id)\
                .filter(ReeBill.issued == 0, ReeBill.version == 0).subquery()
        min_sequence = session.query(unissued_v0_reebills.c.customer_id.label('customer_id'),
                func.min(unissued_v0_reebills.c.sequence).label('sequence'))\
                .group_by(unissued_v0_reebills.c.customer_id).subquery()
        reebills = session.query(ReeBill)\
                .filter(ReeBill.customer_id==min_sequence.c.customer_id)\
                .filter(ReeBill.sequence==min_sequence.c.sequence)
        tuples = sorted([(r.customer.account, r.sequence,
                # 'total_charges' of all utility bills attached to each reebill
                session.query(func.sum(UtilBill.total_charges))\
                        .filter(UtilBill.reebills.contains(r)).one()[0])
                for r in reebills.all()],
                # sort by account ascending; worry about performance later
                # (maybe when sort order is actually configurable)
                key=operator.itemgetter(0))
        return tuples, len(tuples)

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

    def choose_next_utilbills(self, session, account, services):
        '''Returns a list of UtilBill objects representing MySQL utility bills
        that should be attached to the next reebill for the given account, one
        for each service name in 'services'.'''
        customer = self.get_customer(session, account)
        last_sequence = self.last_sequence(session, account)

        # if there is at least one reebill, we can choose utilbills following
        # the end dates of the ones attached to that reebill. if not, start
        # looking for utilbills at the beginning of time.
        if last_sequence:
            last_reebill = self.get_reebill(session, account, last_sequence)
            last_utilbills = session.query(UtilBill)\
                    .filter(UtilBill.reebills.contains(last_reebill)).all()
            service_iter = ((ub.service, ub.period_end) for ub in
                    last_utilbills if ub.service in services)
        else:
            last_utilbills = None
            service_iter = ((service, date.min) for service in services)

        next_utilbills = []

        for service, period_end in service_iter:
            # find the next unattached utilbill for this service
            try:
                utilbill = session.query(UtilBill).filter(
                        UtilBill.customer==customer, UtilBill.service==service,
                        UtilBill.period_start>=period_end)\
                        .filter(not_(UtilBill.reebills.any()))\
                        .order_by(asc(UtilBill.period_start)).first()
            except NoResultFound:
                # If the utilbill is not found, then the rolling process can't proceed
                raise Exception('No new %s utility bill found' % service)
            else:
                if not utilbill:
                    # If the utilbill is not found, then the rolling process can't proceed
                    raise Exception('No new %s utility bill found' % service)

            # Second, calculate the time gap between the last attached utilbill's end date and the next utilbill's start date.
            # If there is a gap of more than one day, then someone may have mucked around in the database or another issue
            # arose. In any case, it suggests missing data, and we don't want to proceed with potentially the wrong
            # utilbill.
            time_gap = utilbill.period_start - period_end
            # Note that the time gap only matters if the account HAD a previous utilbill. For a new account, this isn't the case.
            # Therefore, make sure that new accounts don't fail the time gap condition
            if last_utilbills is not None and time_gap > timedelta(days=1):
                raise Exception('There is a gap of %d days before the next %s utility bill found' % (abs(time_gap.days), service))
            elif utilbill.state == UtilBill.Hypothetical:
                # Hypothetical utilbills are not an acceptable basis for a reebill. Only allow a roll to subsequent reebills if
                # the next utilbill(s) have been received or estimated
                raise Exception("The next %s utility bill exists but has not been fully estimated or received" % service)

            # Attach if no failure condition arose
            next_utilbills.append(utilbill)

        # This may be an irrelevant check, but if no specific exceptions were
        # raised and yet there were no utilbills selected for attachment, there
        # is a problem
        if not next_utilbills:
            raise Exception('No qualifying utility bills found for account #%s' % account)

        return next_utilbills

    
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
                    utility, rate_class, None, None, None, period_start=start,
                    period_end=end)
            # put it in the database
            session.add(utilbill)

    def trim_hypothetical_utilbills(self, session, account, service):
        '''Deletes hypothetical utility bills for the given account and service
        whose periods precede the start date of the earliest non-hypothetical
        utility bill or follow the end date of the last utility bill.'''
        customer = session.query(Customer).filter(Customer.account==account) \
                .one()
        first_real_utilbill = session.query(UtilBill)\
                .filter(UtilBill.customer==customer)\
                .filter(UtilBill.state!=UtilBill.Hypothetical)\
                .order_by(asc(UtilBill.period_start))[0]
        last_real_utilbill = session.query(UtilBill)\
                .filter(UtilBill.customer==customer)\
                .filter(UtilBill.state!=UtilBill.Hypothetical)\
                .order_by(desc(UtilBill.period_start))[0]
        hypothetical_utilbills = session.query(UtilBill)\
                .filter(UtilBill.customer==customer)\
                .filter(UtilBill.state==UtilBill.Hypothetical)\
                .order_by(asc(UtilBill.period_start)).all()

        for hb in hypothetical_utilbills:
            # delete if entire period comes before end of first real bill or
            # after start of last real bill
            if (hb.period_start <= first_real_utilbill.period_end \
                    and hb.period_end <= first_real_utilbill.period_end)\
                    or (hb.period_end >= last_real_utilbill.period_start\
                    and hb.period_start >= last_real_utilbill.period_start):
                session.delete(hb)

    def get_last_real_utilbill(self, session, account, end, service=None,
            utility=None, rate_class=None):
        '''Returns the latest_ending non-Hypothetical UtilBill whose
        end date is before/on 'end', optionally with the given service,
        utility, and rate class.'''
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
        result = cursor.order_by(UtilBill.period_end).first()
        if result is None:
            raise NoSuchBillException
        return result

    def create_payment(self, session, account, date_applied, description,
            credit):
        '''Adds a new payment, returns the new Payment object.'''
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        new_payment = Payment(customer, datetime.utcnow(), date_applied,
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
        and before 'end' (today by default), as a Decimal. If 'start' is none,
        the beginning of the interval extends to the beginning of time.'''
        payments = session.query(Payment)\
                .filter(Payment.customer==self.get_customer(session, account))\
                .filter(Payment.date_applied < end)
        if start is not None:
            payments = payments.filter(Payment.date_applied >= start)
        return Decimal(sum(payment.credit for payment in payments.all()))

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

if __name__ == '__main__':
    # verify that SQLAlchemy setup is working
    s = StateDB(host='localhost', database='skyline_dev', user='dev', password='dev')
    session = s.session()
    print session.query(Customer).all()
