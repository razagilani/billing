#!/usr/bin/python
"""
Utility functions to interact with state database
"""
import os, sys
import itertools
import datetime
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
from sqlalchemy import func
from db_objects import Customer, UtilBill, ReeBill, Payment, StatusDaysSince, StatusUnbilled
from billing.processing.exceptions import BillStateError
sys.stdout = sys.stderr

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

def guess_utilbills_and_end_date(session, account, start_date):
    '''Returns a tuple (end_date, [utilbills]): a list of utility bills that
    will probably be associated with a newly-created reebill for the customer
    given by 'account' starting on 'start_date', and a guess for the reebills'
    end date.'''
    # TODO:25731853 test this method with multi-service customers. it works very well
    # for customers with one utility service, but the more utility bills the
    # customer has, the less accurate it will be.

    # Rich added this because of bug 26512637, which is really a data problem
    # (reebill period dates are missing)
    # TODO remove this because it's a temporary workaround
    if start_date == None:
        print >> sys.stderr, 'guess_utilbills_and_end_date got start_date == None'
        return (None, []) 

    # get length of last reebill (note that we don't store dates for reebills
    # in MySQL)
    customer = session.query(Customer).filter(Customer.account==account).one()
    previous_reebills = session.query(ReeBill) \
            .filter(ReeBill.customer_id==customer.id) \
            .order_by(desc(ReeBill.sequence))
    try:
        # get last reebill. note that SQLALchemy cursor object has no len (you
        # have to issue another query with func.count)
        last_reebill = previous_reebills[0]
    except IndexError:
        # if there are no previous bills, guess 30 days
        # TODO make this guess better?
        length = timedelta(days=30)
    else:
        # otherwise, get length of last bill period
        last_reebill_utilbills = session.query(UtilBill) \
                .filter(UtilBill.reebill_id==last_reebill.id)
        if list(last_reebill_utilbills) == []:
            raise Exception("Can't determine new reebill period without "
                    + "utility bills attached to the last reebill")
        earliest_start = min(ub.period_start for ub in last_reebill_utilbills)
        latest_end = max(ub.period_end for ub in last_reebill_utilbills)
        length = (latest_end - earliest_start)

    # first guess that this reebill's period has the same length as the last.
    # this guess will be adjusted to match the closest utility bill end date
    # after 'start_date', if there are any such utility bills.
    probable_end_date = start_date + length

    # get all utility bills that end after start_date
    utilbills_after_start_date = session.query(UtilBill) \
            .filter(UtilBill.customer_id==customer.id) \
            .filter(UtilBill.period_end > start_date).all()

    # if there are no utility bills that might be associated with this reebill,
    # we can't guess very well--just assume that this reebill's period will be
    # exactly the same length as its predecessor's.
    if len(utilbills_after_start_date) == 0:
        return probable_end_date, []

    # otherwise, adjust the guess to the closest utility bill end date (either
    # forward or back); return that date and all utilbills that end in the date
    # interval (start_date, probable_end_date].
    probable_end_date = min([u.period_end for u in utilbills_after_start_date],
            key = lambda x: abs(probable_end_date - x))
    return probable_end_date, [u for u in utilbills_after_start_date if
            u.period_end <= probable_end_date]

class StateDB:

    config = None

    def __init__(self, host, database, user, password, db_connections=5):
        # put "echo=True" in the call to create_engine to print the SQL
        # statements that are executed
        engine = create_engine('mysql://%s:%s@%s:3306/%s' % (user, password,
                host, database), pool_recycle=3600, pool_size=db_connections)
        self.engine = engine
        metadata = MetaData(engine)

        # table objects loaded automatically from database
        status_days_since_view = Table('status_days_since', metadata, autoload=True)
        utilbill_table = Table('utilbill', metadata, autoload=True)
        reebill_table = Table('reebill', metadata, autoload=True)
        utilbill_reebill_table = Table('utilbill_reebill', metadata, autoload=True)
        customer_table = Table('customer', metadata, autoload=True)
        payment_table = Table('payment', metadata, autoload=True)

        # mappings
        # note that a "relationship" between two tables should be defined on
        # only one of its members; the property used to access rows in that
        # table by by a row of the other table is defined via the "backref"
        # argument.
        # http://docs.sqlalchemy.org/en/rel_0_8/orm/relationships.html
        mapper(StatusDaysSince,
                status_days_since_view,primary_key=[status_days_since_view.c.account])
        mapper(Customer, customer_table, properties={
            'utilbills': relationship(UtilBill, backref='customer'),
            'reebills': relationship(ReeBill, backref='customer')
        })
        mapper(ReeBill, reebill_table, properties={
            'utilbills': relationship(UtilBill,
                    secondary=utilbill_reebill_table, backref='reebills',
                    lazy='joined')
        })
        mapper(UtilBill, utilbill_table, properties={
        })
        mapper(Payment, payment_table, properties={
            'customer': relationship(Customer, backref='payment')
        })


        # To turn logging on
        import logging
        logging.basicConfig()
        #logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
        #logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)

        # session
        # global variable for the database session: SQLAlchemy will give an error if
        # this is created more than once, so don't call _getSession() anywhere else
        # wrapped by scoped_session for thread contextualization
        # http://docs.sqlalchemy.org/en/latest/orm/session.html#unitofwork-contextual
        self.session = scoped_session(sessionmaker(bind=engine, autoflush=True))

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
            utilbill.reebill = reebill
            utilbill.processed = True

    def is_attached(self, session, account, sequence, nonexistent=None):
        '''Returns True iff the given reebill has utility bills attached to it
        in MySQL. If 'nonexistent' is given, that value will be returned if the
        reebill is not present in the state database (e.g. False when you want
        non-existent bills to be treated as unissued).'''
        try:
            customer = self.get_customer(session, account)
            reebill = session.query(ReeBill).filter(ReeBill.customer==customer)\
                    .filter(ReeBill.sequence==sequence).one()
            num_utilbills = session.query(UtilBill)\
                    .filter(UtilBill.reebill==reebill).count()
        except NoResultFound:
            if nonexistent is not None:
                return nonexistent
            raise
        return num_utilbills >= 1

    def utilbills_for_reebill(self, session, account, sequence):
        '''Returns all utility bills for the reebill given by account,
        sequence.'''
        customer = session.query(Customer).filter(Customer.account==account).one()
        reebill = session.query(ReeBill).filter(ReeBill.customer==customer)\
                .filter(ReeBill.sequence==sequence).one()
        utilbills = session.query(UtilBill).filter(UtilBill.reebill==reebill)\
                .order_by(UtilBill.period_start)
        return utilbills.all()

    def delete_reebill(self, session, account, sequence):
        '''Deletes the latest version of the given reebill, if it's not
        issued.'''
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        reebill = session.query(ReeBill)\
                .filter(ReeBill.customer==customer) \
                .filter(ReeBill.sequence==sequence).one()
        if self.is_issued(session, account, sequence):
            raise Exception("Can't delete an issued reebill")
        
        # if the version is 0, detach all utility bills. otherwise leave them
        # as they are, because the attachment needs to be preserved for the
        # decremented version.
        # NOTE see https://www.pivotaltracker.com/story/show/31629749
        if reebill.max_version == 0:
            for utilbill in session.query(UtilBill)\
                    .filter(UtilBill.reebill==reebill):
                utilbill.reebill = None

        if reebill.max_version > 0:
            # all versions except the last are considered issued, so decrement
            # max_version and set issued to true
            reebill.max_version -= 1
            reebill.issued = 1
        else:
            # there's only one version, so really delete it
            session.delete(reebill)

    def max_version(self, session, account, sequence):
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        reebill = session.query(ReeBill)\
                .filter(ReeBill.customer==customer)\
                .filter(ReeBill.sequence==sequence).one()
        # SQLAlchemy returns a "long" here for some reason, so convert to int
        return int(reebill.max_version)

    def max_issued_version(self, session, account, sequence):
        '''Returns the greatest version of the given reebill that has been
        issued. (This should differ by at most 1 from the maximum version
        overall, since a new version can't be created if the last one hasn't
        been issued.) If no version has ever been issued, returns None.'''
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        reebill = session.query(ReeBill)\
                .filter(ReeBill.customer==customer)\
                .filter(ReeBill.sequence==sequence).one()
        # SQLAlchemy returns a "long" here for some reason, so convert to int
        if reebill.issued == 1:
            return int(reebill.max_version)
        elif reebill.max_version == 0:
            return None
        else:
            return int(reebill.max_version - 1)
        
    def increment_version(self, session, account, sequence):
        '''Incrementes the max_version of the given issued reebill (to indicate
        that a new version was successfully created). After the new version is
        created, the reebill is no longer issued, because the newest version
        has not been issued.'''
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        reebill = session.query(ReeBill)\
                .filter(ReeBill.customer==customer)\
                .filter(ReeBill.sequence==sequence).one()
        if not self.is_issued(session, account, sequence):
            raise ValueError(("Can't increment version of %s-%s because "
                    "version %s is not issued yet") % (account, sequence,
                        reebill.max_version))
        reebill.issued = 0
        reebill.max_version += 1

    def get_unissued_corrections(self, session, account):
        '''Returns a list of (sequence, max_version) pairs for bills that have
        versions > 0 that have not been issued.'''
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        reebills = session.query(ReeBill)\
                .filter(ReeBill.customer==customer)\
                .filter(ReeBill.max_version > 0)\
                .filter(ReeBill.issued==0).all()
        return [(int(reebill.sequence), int(reebill.max_version)) for reebill
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
        # the database) rebill needs to be primed otherwise the last sequence
        # for a new bill is None. Design a solution to this issue.
        if max_sequence is None:
            max_sequence =  0
        return max_sequence
        
    def last_issued_sequence(self, session, account, include_corrections=False):
        '''Returns the sequence of the last issued reebill for 'account', or 0
        if there are no issued reebills.'''
        customer = session.query(Customer).filter(Customer.account==account).one()
        if include_corrections:
            filter_logic = sqlalchemy.or_(ReeBill.issued==1, sqlalchemy.and_(ReeBill.issued==0, ReeBill.max_version>0))
        else:
            filter_logic = ReeBill.issued==1

        max_sequence = session.query(sqlalchemy.func.max(ReeBill.sequence)) \
                .filter(ReeBill.customer_id==customer.id) \
                .filter(filter_logic).one()[0]
        if max_sequence is None:
            max_sequence = 0
        return max_sequence

    def last_utilbill_end_date(self, session, account):
        '''Returns the end date of the latest utilbill for the customer given
        by 'account', or None if there are no utilbills.'''
        customer = session.query(Customer).filter(Customer.account==account).one()
        query_results = session.query(sqlalchemy.func.max(UtilBill.period_end)) \
                .filter(UtilBill.customer_id==customer.id).one()
        if len(query_results) > 0:
            return query_results[0]
        return None

    def new_rebill(self, session, account, sequence, max_version=0):
        '''Creates a new ReeBill row in the database and returns the new
        ReeBill object corresponding to it.'''
        customer = session.query(Customer).filter(Customer.account==account).one()
        new_reebill = ReeBill(customer, sequence, max_version)
        session.add(new_reebill)
        return new_reebill

    def issue(self, session, account, sequence):
        '''Marks the given reebill as issued. Does not set the issue date or
        due date (which are in Mongo).'''
        customer = session.query(Customer).filter(Customer.account==account).one()
        reeBill = session.query(ReeBill) \
                .filter(ReeBill.customer_id==customer.id) \
                .filter(ReeBill.sequence==sequence).one()
        reeBill.issued = 1

    def is_issued(self, session, account, sequence, version='max',
            nonexistent=None):
        '''Returns true if the reebill given by account, sequence, and version
        (latest version by default) has been issued, false otherwise. If
        'nonexistent' is given, that value will be returned if the reebill is
        not present in the state database (e.g. False when you want
        non-existent bills to be treated as unissued).'''
        try:
            customer = session.query(Customer)\
                    .filter(Customer.account==account).one()
            reebill = session.query(ReeBill) \
                    .filter(ReeBill.customer_id==customer.id) \
                    .filter(ReeBill.sequence==sequence).one()
        except NoResultFound:
            if nonexistent is not None:
                return nonexistent
            raise
        if version == 'max':
            # NOTE: reebill.issued is an int, and it converts the entire
            # expression to an int unless explicitly cast! see
            # https://www.pivotaltracker.com/story/show/35965271
            return bool(reebill.issued == 1)
        elif isinstance(version, int):
            # any version prior to the latest is assumed to be issued, since
            # otherwise the latest version could not have been created
            return bool((version < reebill.max_version) \
                    or (version == reebill.max_version and reebill.issued))
        else:
            raise ValueError('Unknown version specifier "%s"' % version)

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

    def listAllIssuableReebillInfo(self, session, **kwargs):
        unissued = session.query(ReeBill.sequence.label('sequence'), ReeBill.customer_id.label('customer_id')).filter(ReeBill.issued == 0, ReeBill.max_version == 0).subquery('unissued')
        minseq = session.query(unissued.c.customer_id.label('customer_id'), func.min(unissued.c.sequence).label('sequence')).group_by(unissued.c.customer_id).subquery('minseq')
        query = session.query(Customer.account, ReeBill.sequence, UtilBill.total_charges).filter(ReeBill.sequence == minseq.c.sequence).filter(ReeBill.customer_id == minseq.c.customer_id).filter(UtilBill.customer_id == Customer.id).filter(UtilBill.reebill_id == ReeBill.id)

        slice = query.order_by(asc(Customer.account)).all()
        count = query.count()
        return slice, count

    def list_issued_utilbills_for_account(self, session, account):
        utilbill_info_table = session.query(UtilBill.id, UtilBill.total_charges, UtilBill.service, UtilBill.period_start, UtilBill.period_end, UtilBill.reebill_id, Customer.account).filter(Customer.id == UtilBill.customer_id, Customer.account == account).subquery("utilbill_info")
        Utilbill_info = utilbill_info_table.c
        matching_utilbills = session.query(Utilbill_info.account, ReeBill.sequence, ReeBill.max_version, Utilbill_info.id, Utilbill_info.service, Utilbill_info.period_start, Utilbill_info.period_end).filter(Utilbill_info.reebill_id == ReeBill.id, ReeBill.issued == 1)
        first_date = None
        last_date = None
        if matching_utilbills.count() > 0:
            first_date = matching_utilbills.order_by(Utilbill_info.period_start)[0].period_start
            last_date = matching_utilbills.order_by(Utilbill_info.period_end)[-1].period_end
        return (matching_utilbills.all(), first_date, last_date)

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

    def get_reebill(self, session, account, sequence):

        query = session.query(ReeBill).join(Customer) \
            .filter(Customer.account==account) \
            .filter(ReeBill.sequence==sequence).one()

        return query

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
            reebill = self.get_reebill(session, account, last_sequence)
            last_utilbills = session.query(UtilBill).filter(UtilBill.reebill_id==reebill.id).all()
            service_iter = ((ub.service, ub.period_end) for ub in last_utilbills if ub.service in services)
        else:
            last_utilbills = None
            service_iter = ((service, date.min) for service in services)

        next_utilbills = []

        for service, period_end in service_iter:
            # find the next unattached utilbill for this service
            try:
                utilbill = session.query(UtilBill).filter(
                        UtilBill.customer==customer, UtilBill.service==service,
                        UtilBill.period_start>=period_end, UtilBill.reebill_id
                        == None).order_by(asc(UtilBill.period_start)).first()
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

        # This may be an irrelevant check, but if no specific exceptions were raised and yet there were no
        # utilbills selected for attachment, there is a problem
        if not next_utilbills:
            raise Exception('No qualifying utility bills found for account #%s' % account)

        return next_utilbills

    def record_utilbill_in_database(self, session, account, service,
            begin_date, end_date, total_charges, date_received, state=UtilBill.Complete):
        '''Inserts a row into the utilbill table when a utility bill file has
        been uploaded. The bill is Complete by default but can can have other
        states (see comment in db_objects.UtilBill for explanation of utility
        bill states). The bill is initially marked as un-processed.'''
        # get customer id from account number
        customer = session.query(Customer).filter(Customer.account==account) \
                .one()

        ## new utility bill that will be uploaded (if it's allowed)
        #new_utilbill = UtilBill(customer, state, service,
                #period_start=begin_date, period_end=end_date,
                #date_received=date_received)
        # NOTE: if new_utilbill is created here, but not added, much less
        # committed, it appears as a result in the query below, triggering an
        # error message. 26147819

        # get existing bills matching dates and service
        # (there should be at most one, but you never know)
        existing_bills = session.query(UtilBill) \
                .filter(UtilBill.customer_id==customer.id) \
                .filter(UtilBill.service==service) \
                .filter(UtilBill.period_start==begin_date) \
                .filter(UtilBill.period_end==end_date)

        if list(existing_bills) == []:
            # nothing to replace; just upload the bill
            new_utilbill = UtilBill(customer, state, service,
                    period_start=begin_date, period_end=end_date,
                    total_charges=total_charges, date_received=date_received)
            session.add(new_utilbill)
        elif len(list(existing_bills)) > 1:
            raise Exception(("Can't upload a bill for dates %s, %s because"
                    " there are already %s of them") % (begin_date, end_date,
                    len(list(existing_bills))))
        else:
            # now there is one existing bill with the same dates. if state is
            # "more final" than an existing non-final bill that matches this
            # one, replace that bill
            # TODO 38385969: is this really a good idea?
            # (we can compare with '>' because states are ordered from "most
            # final" to least (see db_objects.UtilBill)
            bills_to_replace = existing_bills.filter(UtilBill.state > state)

            if list(bills_to_replace) == []:
                # TODO this error message is kind of obscure
                raise Exception(("Can't upload a utility bill for dates %s,"
                    " %s because one already exists with a more final"
                    " state than %s") % (begin_date, end_date, state))
            bill_to_replace = bills_to_replace.one()
                
            # now there is exactly one bill with the same dates and its state is
            # less final than the one being uploaded, so replace it.
            session.delete(bill_to_replace)
            new_utilbill = UtilBill(customer, state, service,
                    period_start=begin_date, period_end=end_date,
                    total_charges=total_charges, date_received=date_received)
            session.add(new_utilbill)
    
    def fill_in_hypothetical_utilbills(self, session, account, service,
            begin_date, end_date):
        '''Creates hypothetical utility bills in MySQL covering the period
        [begin_date, end_date).'''
        # get customer id from account number
        customer = session.query(Customer).filter(Customer.account==account) \
                .one()

        for (start, end) in guess_utilbill_periods(begin_date, end_date):
            # make a UtilBill
            utilbill = UtilBill(customer, state=UtilBill.Hypothetical,
                    service=service, period_start=start, period_end=end)
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
