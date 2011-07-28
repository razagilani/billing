#!/usr/bin/python
"""
Utility functions to interact with state database
"""
import os, sys
sys.stdout = sys.stderr
import MySQLdb
from optparse import OptionParser
import db
from db import Customer, UtilBill, ReeBill
import sqlalchemy

# TODO: make configurable

class StateDB:

    config = None

    def __init__(self, config):
        self.config = config
        pass

    def commit_bill(self, account, sequence, start, end):
        # get customer id from account and the reebill from account and sequence
        customer = db.session.query(Customer).filter(Customer.account==account).one()
        reebill = db.session.query(ReeBill).filter(ReeBill.customer==customer)\
                .filter(ReeBill.sequence==sequence).one()

        # get all utilbills for this customer whose dates are between 'start'
        # and 'end' (inclusive)
        utilbills = db.session.query(UtilBill) \
                .filter(UtilBill.customer==customer)\
                .filter(UtilBill.period_start>=start)\
                .filter(UtilBill.period_end<=end).all()
        
        # update 'reebill_id' and 'processed' for each utilbill found
        for utilbill in utilbills:
            utilbill.reebill = reebill
            utilbill.processed = True
        # TODO commit has to come out of here
        db.session.commit()


    def discount_rate(self, account):
        # one() raises an exception if more than one row was found
        return db.session.query(Customer).filter_by(account=account).one().discountrate

    def last_sequence(self, account):

        customer = db.session.query(Customer).filter(Customer.account==account).one()

        max_sequence = db.session.query(sqlalchemy.func.max(ReeBill.sequence)) \
                .filter(ReeBill.customer_id==customer.id).one()[0]

        # TODO: because of the way 0.xml templates are made (they are not in the database) rebill needs to be 
        # primed otherwise the last sequence for a new bill is None. Design a solution to this issue.
        if max_sequence is None:
            return 0

        return max_sequence
        
    def new_rebill(self, account, sequence):

        customer = db.session.query(Customer).filter(Customer.account==account).one()
        new_reebill = ReeBill(customer, sequence)

        db.session.add(new_reebill)
        # TODO commit has to come out of here
        db.session.commit()

    def issue(self, account, sequence):
        customer = db.session.query(Customer).filter(Customer.account==account).one()
        reeBill = db.session.query(ReeBill).filter(ReeBill.customer_id==customer.id).filter(ReeBill.sequence==sequence).one()
        reeBill.issued = 1
        # TODO commit has to come out of here
        db.session.commit()

    def listAccounts(self):
        # SQLAlchemy returns a list of tuples, so convert it into a plain list
        return map((lambda x: x[0]), db.session.query(Customer.account).all())

    def listSequences(self, account):
        # TODO: figure out how to do this all in one query. many SQLAlchemy
        # subquery examples use multiple queries but that shouldn't be
        # necessary
        customer = db.session.query(Customer).filter(Customer.account==account).one()
        sequences = db.session.query(ReeBill.sequence).filter(ReeBill.customer_id==customer.id).all()

        # sequences is a list of tuples of numbers, so convert it into a plain list
        return map((lambda x: x[0]), sequences)


    '''Queries the database for account, start date, and
    end date of bills in a slice of the utilbills table; returns the slice and the
    total number of rows in the table (for paging).'''
    def getUtilBillRows(self, start, limit):
        # SQLAlchemy query to get account & dates for all utilbills
        query = db.session.query(Customer.account, UtilBill.period_start, \
                UtilBill.period_end).filter(UtilBill.customer_id==Customer.id)

        # SQLAlchemy does SQL 'limit' with Python list slicing
        slice = query[start:start + limit]

        # count total number of utilbills (note that some rows in utilbill may
        # have null customer_ids, even though that's not supposed to happen)
        count = query.count()
        return slice, count

if __name__ == "__main__":

    parser = OptionParser()

    parser.add_option("--host", dest="host", help="Database Host")
    parser.add_option("--db", dest="db", help="Database")
    parser.add_option("--user", dest="user", help="User")
    parser.add_option("--password", dest="password", help="Password")
    parser.add_option("--account", dest="account", help="Customer billing account")
    parser.add_option("--sequence", dest="sequence", help="Bill sequence number")
    parser.add_option("--start", dest="start", help="RE bill period start")
    parser.add_option("--end", dest="end", help="RE bill period end")

    (options, args) = parser.parse_args()
    # some testing code that no longer works
    #issue(options.host, options.db, options.user, options.password, options.account, options.sequence)

