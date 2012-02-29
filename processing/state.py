#!/usr/bin/python
"""
Utility functions to interact with state database
"""
import os, sys
import datetime
from datetime import timedelta
import sqlalchemy
from sqlalchemy import Table, Integer, String, Float, MetaData, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import mapper, sessionmaker, scoped_session
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import and_
from db_objects import Customer, UtilBill, ReeBill, Payment, StatusDaysSince, StatusUnbilled
sys.stdout = sys.stderr

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
    '''Returns a tuple ([utilbills], end_date): a list of utility bills that
    will probably be associated with a newly-created reebill for the customer
    given by 'account' starting on 'start_date', and a guess for the reebills'
    end date.'''
    # TODO:25731853 test this method with multi-service customers. it works very well
    # for customers with one utility service, but the more utility bills the
    # customer has, the less accurate it will be.

    # get length of last reebill (note that we don't store dates for reebills
    # in MySQL)
    customer = session.query(Customer).filter(Customer.account==account).one()
    last_reebill = session.query(ReeBill) \
            .filter(ReeBill.customer_id==customer.id) \
            .order_by(ReeBill.sequence)[0]
    last_reebill_utilbills = session.query(UtilBill).filter(UtilBill.rebill_id==last_reebill.id)
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

    def __init__(self, config):

        self.config = config

        '''This returns a database session object for querying the database. Don't call
        it from outside this file, because the session should only be created
        once. Instead, use the global variable 'session' above.'''
        host = config['host']
        db = config['database']
        user = config['user']
        password = config['password']

        # put "echo=True" in the call to create_engine to print the SQL
        # statements that are executed
        engine = create_engine('mysql://%s:%s@%s:3306/%s' % (user, password,
                host, db), pool_recycle=3600)
        metadata = MetaData(engine)

        # table objects loaded automatically from database
        status_days_since_view = Table('status_days_since', metadata, autoload=True)
        status_unbilled_view = Table('status_unbilled', metadata, autoload=True)
        utilbill_table = Table('utilbill', metadata, autoload=True)
        reebill_table = Table('rebill', metadata, autoload=True)
        customer_table = Table('customer', metadata, autoload=True)
        payment_table = Table('payment', metadata, autoload=True)

        # mappings
        mapper(StatusDaysSince, status_days_since_view,primary_key=[status_days_since_view.c.account])
        mapper(StatusUnbilled, status_unbilled_view, primary_key=[status_unbilled_view.c.account])

        mapper(Customer, customer_table, \
                properties={
                    'utilbills': relationship(UtilBill, backref='customer'), \
                    'reebills': relationship(ReeBill, backref='customer')
                })

        mapper(ReeBill, reebill_table)

        mapper(UtilBill, utilbill_table, \
                properties={
                    # "lazy='joined'" makes SQLAlchemy eagerly load utilbill customers
                    'reebill': relationship(ReeBill, backref='utilbill', lazy='joined')
                })

        mapper(Payment, payment_table, \
                properties={
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
        self.session = scoped_session(sessionmaker(bind=engine, autoflush=True))

    def new_account(self, session, name, account, discount_rate):

        new_customer = Customer(name, account, discount_rate)

        session.add(new_customer)

        return new_customer


    def attach_utilbills(self, session, account, sequence, start, end):
        '''Records in MySQL the association between the reebill given by
        'account', 'sequence' and all utilbills belonging to that customer
        whose entire periods are within the date interval [start, end]. The
        utility bills are marked as processed.'''
        # get customer id from account and the reebill from account and sequence
        customer = session.query(Customer).filter(Customer.account==account).one()
        reebill = session.query(ReeBill).filter(ReeBill.customer==customer)\
                .filter(ReeBill.sequence==sequence).one()

        # get all utilbills for this customer whose dates are between 'start'
        # and 'end' (inclusive)
        utilbills = session.query(UtilBill) \
                .filter(UtilBill.customer==customer)\
                .filter(UtilBill.period_start>=start)\
                .filter(UtilBill.period_end<=end).all()
        
        # update 'reebill_id' and 'processed' for each utilbill found
        for utilbill in utilbills:
            utilbill.reebill = reebill
            utilbill.processed = True

    def delete_reebill(self, session, account, sequence):
        # TODO add branch, which MySQL doesn't have yet:
        # https://www.pivotaltracker.com/story/show/24374911 

        # get customer id from account
        customer = session.query(Customer).filter(Customer.account==account).one()

        # look up reebill by account, sequence
        reebill = session.query(ReeBill).filter(ReeBill.customer==customer) \
                .filter(ReeBill.sequence==sequence).one()
        
        # find all utilbills attached to this reebill and detach them
        for utilbill in session.query(UtilBill).filter(UtilBill.reebill==reebill):
            utilbill.reebill = None

        # delete the reebill
        session.delete(reebill)

    def discount_rate(self, session, account):

        # one() raises an exception if more than one row was found
        result = session.query(Customer).filter_by(account=account).one().discountrate

        return result
        
    # TODO: 22598787 branches
    def last_sequence(self, session, account):

        customer = session.query(Customer).filter(Customer.account==account).one()

        max_sequence = session.query(sqlalchemy.func.max(ReeBill.sequence)) \
                .filter(ReeBill.customer_id==customer.id).one()[0]

        # TODO: because of the way 0.xml templates are made (they are not in the database) rebill needs to be 
        # primed otherwise the last sequence for a new bill is None. Design a solution to this issue.
        if max_sequence is None:
            max_sequence =  0

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

    def new_rebill(self, session, account, sequence):
        customer = session.query(Customer).filter(Customer.account==account).one()
        new_reebill = ReeBill(customer, sequence)
        session.add(new_reebill)

    def issue(self, session, account, sequence):
        customer = session.query(Customer).filter(Customer.account==account).one()
        reeBill = session.query(ReeBill) \
                .filter(ReeBill.customer_id==customer.id) \
                .filter(ReeBill.sequence==sequence).one()
        reeBill.issued = 1

    def is_issued(self, session, account, sequence):
        customer = session.query(Customer).filter(Customer.account==account).one()
        reebill = session.query(ReeBill) \
                .filter(ReeBill.customer_id==customer.id) \
                .filter(ReeBill.sequence==sequence).one()
        return reebill.issued == 1

    def account_exists(self, session, account):
        try:
           customer = session.query(Customer).with_lockmode("read").filter(Customer.account==account).one()
        except NoResultFound:
            return False

        return True

    # TODO: 22260579 can we remove this function?
    def listAccounts(self, session):
        
        # SQLAlchemy returns a list of tuples, so convert it into a plain list

        result = map((lambda x: x[0]), session.query(Customer.account).all())

        return result

    def list_accounts(self, session, start, limit):
        
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

    def listReebills(self, session, start, limit, account):

        query = session.query(ReeBill).join(Customer).filter(Customer.account==account)

        slice = query[start:start + limit]
        count = query.count()

        return slice, count

    def list_utilbills(self, session, account, start=None, limit=None):
        '''Queries the database for account, start date, and end date of bills
        in a slice of the utilbills table; returns the slice and the total
        number of rows in the table (for paging). If 'start' is not given, all
        bills are returned. If 'start' is given but 'limit' is not, all bills
        starting with index 'start'. If both 'start' and 'limit' are given,
        returns bills with indices in [start, start + limit).'''

        # SQLAlchemy query to get account & dates for all utilbills
        query = session.query(UtilBill).with_lockmode('read').join(Customer). \
            filter(Customer.account==account).order_by(Customer.account, UtilBill.period_start)

        if start is None:
            return query, query.count()
        if limit is None:
            return query[start:], query.count()
        # SQLAlchemy does SQL 'limit' with Python list slicing
        return query[start:start + limit], query.count()

    def record_utilbill_in_database(self, session, account, begin_date,
            end_date, date_received, state=UtilBill.Complete):
        '''Inserts a row into the utilbill table when a utility bill file has
        been uploaded. The bill is Complete by default but can can have other
        states (see comment in db_objects.UtilBill for explanation of utility
        bill states). The bill is initially marked as un-processed.'''

        print >> sys.stderr, 'state of incoming bill is %s', state

        # get customer id from account number
        customer = session.query(Customer).filter(Customer.account==account).one()

        # make a new UtilBill with the customer id and dates (UtilBill
        # constructor defaults to processed=False)
        utilbill = UtilBill(customer, state, period_start=begin_date,
                period_end=end_date, date_received=date_received)

        # put the new UtilBill in the database
        session.add(utilbill)
    
    def fill_in_hypothetical_utilbills(self, session, account, begin_date,
            end_date):
        '''Creates hypothetical utility bills in MySQL covering the period
        [begin_date, end_date).'''
        # get customer id from account number
        customer = session.query(Customer).filter(Customer.account==account) \
                .one()

        for (start, end) in guess_utilbill_periods(begin_date, end_date):
            # make a UtilBill
            utilbill = UtilBill(customer, state=UtilBill.Hypothetical,
                    period_start=start, period_end=end)
            # put it in the database
            session.add(utilbill)

    def create_payment(self, session, account, date, description, credit):
        customer = session.query(Customer).filter(Customer.account==account).one()
        new_payment = Payment(customer, date, description, credit)

        session.add(new_payment)

        return new_payment

    def update_payment(self, session, oid, date, description, credit):
        # get the object
        payment = session.query(Payment).filter(Payment.id == oid).one()

        # update the object
        # TODO: is there a better way to update an object from a dict from the post?
        # TODO: this type parsing should definitely be done in Payment
        from datetime import datetime
        from decimal import Decimal
        # TODO: EXT posts in this format - figure out how to control dates better
        payment.date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S").date()
        payment.description = description
        payment.credit = Decimal(credit)

    def delete_payment(self, session, oid):
        # get the object
        payment = session.query(Payment).filter(Payment.id == oid).one()

        session.delete(payment)

    def find_payment(self, session, account, periodbegin, periodend):
        '''periodbegin and periodend must be non-overlapping between bills.
        This is in direct opposition to the reebill period concept, which is a
        period that covers all services for a given reebill and thus overlap
        between bills.  Therefore, a non overlapping period could be just the
        first utility service on the reebill. If the periods overlap, payments
        will be applied more than once. See 11093293'''
        payments = session.query(Payment).filter(Payment.customer_id == Customer.id) \
            .filter(Customer.account == account) \
            .filter(and_(Payment.date >= periodbegin, Payment.date < periodend)) \
            .all()
        return payments
        

    def payments(self, session, account):
        payments = session.query(Payment).join(Customer).filter(Customer.account==account).all()
        return payments

    def retrieve_status_days_since(self, session, start, limit):
        # SQLAlchemy query to get account & dates for all utilbills
        query = session.query(StatusDaysSince).with_lockmode("read")

        # SQLAlchemy does SQL 'limit' with Python list slicing
        slice = query[start:start + limit]

        count = query.count()

        return slice, count

    def retrieve_status_unbilled(self, session, start, limit):
        # SQLAlchemy query to get account & dates for all utilbills
        query = session.query(StatusUnbilled).with_lockmode("read")

        # SQLAlchemy does SQL 'limit' with Python list slicing
        slice = query[start:start + limit]

        count = query.count()

        return slice, count
