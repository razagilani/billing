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

class StateDB:

    config = None

    def __init__(self, config):
        self.config = config
        pass

    def fetch(self, query, params, fetchall = True):
        try:
            conn = MySQLdb.connect(host=self.config["host"], \
                    user=self.config["user"], passwd=self.config["password"], \
                    db=self.config["db"])

            cur = conn.cursor(MySQLdb.cursors.DictCursor)

            cur.execute(query, params)
            print "Number of rows affected: %d" % cur.rowcount

            # TODO: print some sane message about failures
            if fetchall is True:
                return cur.fetchall()
            else:
                return cur.fetchone()

        except MySQLdb.Error:
            print "Database error"
            raise

        except:
            print "Unexpected error:", sys.exc_info()[0]
            raise

        finally:
            if (vars().has_key('cur') is True and type(cur) is MySQLdb.cursors.Cursor):
                cur.close()

            if (vars().has_key('conn') is True and type(conn) is MySQLdb.connections.Connection): 
                conn.commit()
                conn.close()

    def commit_bill(self, account, sequence, start, end):

        #query = "call commit_bill(%s, %s, %s, %s)"
        query = "update utilbill set rebill_id = (select id from rebill where customer_id = (select id from customer where account = %s) and sequence = %s), processed = true where customer_id = (select id from customer where account = %s) and period_start >= %s and period_end <= %s"
        params = (account, sequence, account, start, end)
        return self.fetch(query, params, False)

    def discount_rate(self, account):
        '''
        query = "select discountrate from customer where account = %s"
        params = (account)
        rows = self.fetch(query, params)
        # TODO: error checking...
        return rows[0]['discountrate']
       ''' 
        # one() raises an exception if more than one row was found
        return db.session.query(Customer).filter_by(account=account).one().discountrate

    def last_sequence(self, account):
        query = "select max(sequence) as maxseq from rebill where customer_id = (select id from customer where account = %s)"
        params = (account)
        rows = self.fetch(query, params)
        # TODO: because of the way 0.xml templates are made (they are not in the database) rebill needs to be 
        # primed otherwise the last sequence for a new bill is None. Design a solution to this issue.
        if rows[0]['maxseq'] is None:
            return 0
        return rows[0]['maxseq']
        
    def new_rebill(self, account, sequence):
        query = "insert into rebill (id, sequence, customer_id, issued) values (null, %s, (select id from customer where account = %s),false)" 
        params = (sequence, account)
        # TODO: error checking...
        rows = self.fetch(query, params, False)

    def issue(self, account, sequence):
        query = "update rebill set issued = 1 where sequence = %s and customer_id = (select id from customer where account = %s)"
        params = (sequence, account)
        # TODO: error checking...
        rows = self.fetch(query, params, False)

    def listAccounts(self):
        '''
        query = "select account from customer"
        return self.fetch(query, None, True)
        '''
        return map((lambda x: x[0]), db.session.query(Customer.account).all())

    def listSequences(self, account):
        query = "select sequence from rebill r where r.customer_id = (select id from customer where account = %s)"
        params = (account)
        return self.fetch(query, params, True)

    '''Queries the database for account, start date, and
    end date of bills in a slice of the utilbills table; returns the slice and the
    total number of rows in the table (for paging).'''
    def getUtilBillRows(self, start, limit):
        '''
        # get appropriate slice of table
        query = "select account, period_start, period_end from customer, utilbill where customer.id = utilbill.customer_id limit %s,%s"
        params = (start, limit)

        theSlice = self.fetch(query, params, True)
        
        # count total number of rows in the whole table (not just the slice)
        # note: this must be the exact same query as above, not just "select
        # count(*) from utilbill", which would count rows in utilbill that
        # have null ids even though they don't show up in the query above.
        query = "select count(*) as count from customer, utilbill where customer.id = utilbill.customer_id"

        # TODO any one thing goes wrong, this statement will fail - test values/types more diligently
        totalCount = int(self.fetch(query, None)[0]['count'])
        
        # return the slice (dictionary) and the overall count (integer)
        return theSlice, totalCount
        '''
        query = db.session.query(Customer.account, UtilBill.period_start, \
                UtilBill.period_end).filter(UtilBill.customer_id==Customer.id)
        slice = query[start:start + limit]
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

    issue(options.host, options.db, options.user, options.password, options.account, options.sequence)

