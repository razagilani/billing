#!/usr/bin/python
'''This file contains everything for interacting with the MySQL database.'''
import sqlalchemy
from sqlalchemy import Table, Integer, String, Float, MetaData, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import mapper, sessionmaker
from sqlalchemy.orm import relationship, backref

'''These classes represent the database tables 'customer', 'rebill', and
'utilbill' respectively.'''
class Customer(object):
    def __init__(self, name, account, discountrate):
        self.name = name
        self.account = account
        self.discountrate = discountrate
    def __repr__(self):
        return '<Customer(%s, %s, %s)>' \
                % (self.name, self.account, self.discountrate)
class ReeBill(object):
    def __init__(self, customer, sequence):
        self.customer = customer
        self.sequence = sequence
        self.issued = 0
    def __repr__(self):
        return '<ReeBill(%s, %s, %s)>' \
                % (self.customer, self.sequence, self.issued)
class UtilBill(object):
    def __init__(self, customer, period_start, period_end, \
            estimated, processed, received):
        self.customer = customer
        self.period_start = period_start
        self.period_end = period_end
        self.estimated = estimated
        self.received = received
    def __repr__(self):
        return '<UtilBill(%s, %s, %s)>' \
                % (self.customer, self.period_start, self.period_end)

'''This returns a database session object for querying the database. Don't call
it from outside this file, because the session should only be created
once. Instead, use the global variable 'session' above.'''
def _getSession():
    engine = create_engine('mysql://dev:dev@localhost:3306/skyline')
    #metadata = MetaData() 
    metadata = MetaData(engine)

    # table objects loaded automatically from database
    utilbill_table = Table('utilbill', metadata, autoload=True)
    reebill_table = Table('rebill', metadata, autoload=True)
    customer_table = Table('customer', metadata, autoload=True)

    # mappings
    mapper(Customer, customer_table, \
            properties={
                'utilbills': relationship(UtilBill, backref='customer'), \
                'reebills': relationship(ReeBill, backref='customer')
            })
    mapper(ReeBill, reebill_table)
    mapper(UtilBill, utilbill_table, \
            properties={
                'reebill': relationship(ReeBill, backref='utilbill')
            })

    # session
    return sessionmaker(bind=engine)()

# global variable for the database session: SQLAlchemy will give an error if
# this is created more than once, so don't call _getSession() anywhere else
session = _getSession()

