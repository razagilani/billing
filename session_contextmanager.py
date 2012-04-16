#!/usr/bin/python
'''Prototype/example code for SQLAlchemy database session context manager.'''
import traceback
from billing import mongo
from billing.reebill import render
from billing.processing import state
from billing.processing.db_objects import ReeBill, Customer

class DBSession(object):
    def __init__(self, state_db):
        self.state_db = state_db

    def __enter__(self):
        self.session = self.state_db.session()
        return self.session

    def __exit__(self, type, value, traceback):
        print 'exit: %type={type}, value=%{value}, traceback=%{traceback}'.format(**vars())
        self.session.rollback()

statedb_config = {
    'host': 'localhost',
    'password': 'dev',
    'database': 'skyline_dev',
    'user': 'dev',
    'db_connections': 1
}

state_db = state.StateDB(**statedb_config)


for i in range(5):
    with DBSession(state_db) as session:
        try:
            session = state_db.session()
            accounts = state_db.listAccounts(session)
            print accounts
            customer = session.query(Customer).filter(Customer.account=='10001').one()
            r = ReeBill(customer, 99)
            session.add(r)
            session.commit()
            session.flush()
        except:
            pass
