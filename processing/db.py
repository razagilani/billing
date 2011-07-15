#!/usr/bin/python
import sqlalchemy
from sqlalchemy import Table, Integer, String, Float, MetaData, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import mapper, sessionmaker
from sqlalchemy.orm import relationship, backref

# global variable for the database session: SQLAlchemy will give an error if
# this is created more than once
class Customer(object):
    def __init__(self, name, account, discountrate):
        self.name = name
        self.account = account
        self.discountrate = discountrate

    def __repr__(self):
        return '<Customer(%s, %s, %s)>' \
                % (self.name, self.account, self.discountrate)

class ReeBill(object):
    def __init__(self, sequence, customer_id, issued):
        self.sequence = sequence,
        self.customer_id = customer_id,
        self.issued = issued
    
    def __repr__(self):
        return '<ReeBill(%s, %s, %s)>' \
                % (self.customer_id, self.sequence, str(self.issued))

class UtilBill(object):
    def __init__(self, customer_id, reebill_id, period_start, period_end, \
            estimated, processed, received):
        self.customer_id = customer_id
        self.reebill_id = reebill_id
        self.period_start = period_start
        self.period_end = period_end
        self.estimated = estimated
        self.received = recieved

    def __repr__(self):
        return '<UtilBill(%s, %s, %s)>' \
                % (self.customer_id, self.period_start, str(self.period_end))

def _getSession():
    engine = create_engine('mysql://dev:dev@tyrell:3306/skyline_dev')
    #metadata = MetaData() 
    metadata = MetaData(engine)

    # table objects loaded automatically from database
    utilbill_table = Table('utilbill', metadata, autoload=True)
    reebill_table = Table('rebill', metadata, autoload=True)
    customer_table = Table('customer', metadata, autoload=True)

    # mappings
    mapper(Customer, customer_table, \
            properties={'utilbills': relationship(UtilBill, backref='customer'), \
                        'reebills': relationship(ReeBill, backref='customer')})
    mapper(ReeBill, reebill_table)
    mapper(UtilBill, utilbill_table)

    # session
    return sessionmaker(bind=engine)()

session = _getSession()

