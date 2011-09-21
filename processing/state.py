#!/usr/bin/python
"""
Utility functions to interact with state database
"""
import os, sys
sys.stdout = sys.stderr
import MySQLdb
from optparse import OptionParser

import sqlalchemy
from sqlalchemy import Table, Integer, String, Float, MetaData, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import mapper, sessionmaker, scoped_session
from sqlalchemy.orm import relationship, backref
from sqlalchemy import and_
from db_objects import Customer, UtilBill, ReeBill, Payment, StatusDaysSince, StatusUnbilled

class StateDB:

    config = None

    def __init__(self, config):

        self.config = config

        '''This returns a database session object for querying the database. Don't call
        it from outside this file, because the session should only be created
        once. Instead, use the global variable 'session' above.'''
        host = config['host']
        db = config['db']
        user = config['user']
        password = config['password']

        # put "echo=True" in the call to create_engine to print the SQL statements that are executed
        engine = create_engine('mysql://%s:%s@%s:3306/%s' % (user, password, host, db), pool_recycle=3600)
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
        #import logging
        #logging.basicConfig()
        #logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)

        # session
        # global variable for the database session: SQLAlchemy will give an error if
        # this is created more than once, so don't call _getSession() anywhere else
        # wrapped by scoped_session for thread contextualization
        self.session = scoped_session(sessionmaker(bind=engine, autoflush=True))

    def commit_bill(self, account, sequence, start, end):

        session = self.session()

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

        # TODO commit has to come out of here
        session.commit()


    def discount_rate(self, account):

        session = self.session()

        # one() raises an exception if more than one row was found
        result = session.query(Customer).filter_by(account=account).one().discountrate

        # TODO commit has to come out of here
        session.commit()

        return result

        

    def last_sequence(self, account):

        session = self.session()

        customer = session.query(Customer).filter(Customer.account==account).one()

        max_sequence = session.query(sqlalchemy.func.max(ReeBill.sequence)) \
                .filter(ReeBill.customer_id==customer.id).one()[0]

        # TODO: because of the way 0.xml templates are made (they are not in the database) rebill needs to be 
        # primed otherwise the last sequence for a new bill is None. Design a solution to this issue.
        if max_sequence is None:
            max_sequence =  0

        session.commit()

        return max_sequence
        
    def new_rebill(self, account, sequence):

        session = self.session()

        customer = session.query(Customer).filter(Customer.account==account).one()
        new_reebill = ReeBill(customer, sequence)

        session.add(new_reebill)

        # TODO commit has to come out of here
        session.commit()

    def issue(self, account, sequence):

        session = self.session()

        customer = session.query(Customer).filter(Customer.account==account).one()
        reeBill = session.query(ReeBill).filter(ReeBill.customer_id==customer.id).filter(ReeBill.sequence==sequence).one()
        reeBill.issued = 1

        # TODO commit has to come out of here
        session.commit()

    def listAccounts(self):
        
        session = self.session()

        # SQLAlchemy returns a list of tuples, so convert it into a plain list

        result = map((lambda x: x[0]), session.query(Customer.account).all())

        session.commit()

        return result

    def listSequences(self, account):

        session = self.session()

        # TODO: figure out how to do this all in one query. many SQLAlchemy
        # subquery examples use multiple queries but that shouldn't be
        # necessary
        customer = session.query(Customer).filter(Customer.account==account).one()
        sequences = session.query(ReeBill.sequence).with_lockmode("read").filter(ReeBill.customer_id==customer.id).all()

        # sequences is a list of tuples of numbers, so convert it into a plain list
        result = map((lambda x: x[0]), sequences)

        session.commit()

        return result

    def listReebills(self, start, limit, account):

        session = self.session()

        query = session.query(ReeBill).join(Customer).filter(Customer.account==account)

        slice = query[start:start + limit]
        count = query.count()

        session.commit()

        return slice, count


    '''Queries the database for account, start date, and
    end date of bills in a slice of the utilbills table; returns the slice and the
    total number of rows in the table (for paging).'''
    def list_utilbills(self, start, limit):

        session = self.session()

        # SQLAlchemy query to get account & dates for all utilbills
        query = session.query(UtilBill).with_lockmode('read').join(Customer).order_by(Customer.account, UtilBill.period_start)

        # SQLAlchemy does SQL 'limit' with Python list slicing
        slice = query[start:start + limit]

        count = query.count()

        session.commit()

        return slice, count

    '''Inserts a a row into the utilbill table when the bill file has been
    uploaded.'''
    def insert_bill_in_database(self, account, begin_date, end_date):

        session = self.session()

        # get customer id from account number
        customer = session.query(Customer).filter(Customer.account==account).one()

        # make a new UtilBill with the customer id and dates:
        # reebill_id is NULL in the database because there's no ReeBill
        # associated with this UtilBill yet; estimated is false (0) by default;
        # processed is false because this is a newly updated bill; recieved is
        # true because it's assumed that all bills have been recieved except in
        # unusual cases
        utilbill = UtilBill(customer, period_start=begin_date, period_end=end_date, 
            estimated=False, processed=False, received=True)

        # put the new UtilBill in the database
        session.add(utilbill)

        session.commit()

    def create_payment(self, account, date, description, credit):

        session = self.session()

        customer = session.query(Customer).filter(Customer.account==account).one()
        new_payment = Payment(customer, date, description, credit)

        session.add(new_payment)

        # TODO commit has to come out of here
        session.commit()

        return new_payment

    def update_payment(self, oid, date, description, credit):

        session = self.session()

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

        # TODO commit has to come out of here
        session.commit()

    def delete_payment(self, oid):

        session = self.session()

        # get the object
        payment = session.query(Payment).filter(Payment.id == oid).one()

        session.delete(payment)

        # TODO commit has to come out of here
        session.commit()

    '''periodbegin and periodend must be non-overlapping between bills.  This is in
    direct opposition to the reebill period concept, which is a period that covers
    all services for a given reebill and thus overlap between bills.  Therefore, 
    a non overlapping period could be just the first utility service on the reebill.
    If the periods overlap, payments will be applied more than once. See 11093293'''
    def find_payment(self, account, periodbegin, periodend):

        session = self.session()

        payments = session.query(Payment).filter(Payment.customer_id == Customer.id) \
            .filter(Customer.account == account) \
            .filter(and_(Payment.date >= periodbegin, Payment.date < periodend)) \
            .all()

        session.commit()

        return payments
        

    def payments(self, account):

        session = self.session()

        payments = session.query(Payment).join(Customer).filter(Customer.account==account).all()

        session.commit()

        return payments

    def retrieve_status_days_since(self, start, limit):

        session = self.session()

        # SQLAlchemy query to get account & dates for all utilbills
        query = session.query(StatusDaysSince)

        # SQLAlchemy does SQL 'limit' with Python list slicing
        slice = query[start:start + limit]

        count = query.count()

        session.commit()

        return slice, count

    def retrieve_status_unbilled(self, start, limit):

        session = self.session()

        # SQLAlchemy query to get account & dates for all utilbills
        query = session.query(StatusUnbilled)

        # SQLAlchemy does SQL 'limit' with Python list slicing
        slice = query[start:start + limit]

        count = query.count()

        session.commit()

        return slice, count
