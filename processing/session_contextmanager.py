#!/usr/bin/python
'''SQLAlchemy database session context manager. Use it like:
    with DBSession(state_db) as session:
        # do stuff with database...
        session.commit()
If an exception interrupts the code before session.commit(), the session is
rolled back automatically.
'''
import traceback
import threading
import thread
import time
import random
from sys import stderr

class DBSession(object):
    '''Context manager for using "with" for database session.'''
    def __init__(self, state_db, logger=None):
        '''If 'logger' is given, it will be used to record exceptions that
        caused the context manager to exit.'''
        self.state_db = state_db
        self.logger = logger

    def __enter__(self):
        # session is thread local so we don't need to store it
        session = self.state_db.session()
        return session

    def __exit__(self, exc_type, value, traceback):
        if (exc_type, value, traceback) == (None, None, None):
            # there was no error: auto-commit the database session.
            session = self.state_db.session()
            session.commit()
        else:
            # an exception happened: roll back the session, and log it if
            # there's a logger
            session = self.state_db.session()
            session.rollback()
            if self.logger is not None:
                # 'value' is the exception
                self.logger.error('%s:\n%s' % (value, traceback))

            # NOTE you can return True here to suppress the exception


if __name__ == '__main__':
    class QueryThread(threading.Thread):
        def __init__(self, state_db, number):
            super(QueryThread, self).__init__()
            self.state_db = state_db
            self.number = number

        def run(self):
            with DBSession(self.state_db) as session:
                time.sleep(random.random())
                print 'session is', id(session)
                # some selects
                self.state_db.listAccounts(session)
                customer = session.query(Customer).filter(Customer.account=='10001').one()

                # an insert
                r = ReeBill(customer, self.number)
                session.add(r)

                #session.commit()
                session.flush()
                session.delete(r)
                session.flush()

    global_state_db = state.StateDB(
        host='localhost',
        password='dev',
        database='skyline_dev',
        user='dev',
        db_connections=1
    )

    for i in range(100,200):
        q = QueryThread(global_state_db, i)
        q.start()

    #for i in range(5):
        #with DBSession(state_db) as session:
            #try:
                #session = state_db.session()
                #accounts = state_db.listAccounts(session)
                #print accounts
                #customer = session.query(Customer).filter(Customer.account=='10001').one()
                #r = ReeBill(customer, 99)
                #session.add(r)
                #session.commit()
                #session.flush()
            #except:
                #pass
