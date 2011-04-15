#!/usr/bin/python
"""
Utility functions to interact with state database
"""

import os, sys
import MySQLdb


from optparse import OptionParser


def fetch_all(host, db, user, password, query, params):
    try:
        conn = MySQLdb.connect(host=host, user=user, passwd=password, db=db)

        cur = conn.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(query, params)
        # TODO: print some sane message about failures
        return cur.fetchall()

    except MySQLdb.Error:
        print "Database error"
        raise

    except:
        print "Unexpected error:", sys.exc_info()[0]
        raise

    finally:
        if (vars().has_key('cur') is True and type(cur) is MySQLdb.cursors.Cursor):
            # it is safe to close a cursor multiple times
            cur.close()

        if (vars().has_key('conn') is True and type(conn) is MySQLdb.connections.Connection): 
            conn.close()

def commit_bill(host, db, user, password, account, sequence, start, end):

    query = "call commit_bill(%s, %s, %s, %s)"
    params = (account, sequence, start, end)
    return execute_query(host, db, user, password, query, params)

def discount_rate(host, db, user, password, account):

    query = "select discountrate from customer where account = %s"
    params = (account)
    rows = fetch_all(host, db, user, password, query, params)
    # TODO: error checking...
    return rows[0]['discountrate']

def last_sequence(host, db, user, password, account):
    query = "select max(sequence) as maxseq from rebill where customer_id = (select id from customer where account = %s)"
    params = (account)
    rows = fetch_all(host, db, user, password, query, params)
    # TODO: error checking...
    return rows[0]['maxseq']

if __name__ == "__main__":

    parser = OptionParser()

    parser.add_option("--account", dest="account", help="Customer billing account")
    parser.add_option("--sequence", dest="sequence", help="Bill sequence number")
    parser.add_option("--uri", dest="uri", help="The location of the bill")
    parser.add_option("--start", dest="start", help="RE bill period start")
    parser.add_option("--end", dest="end", help="RE bill period end")

    (options, args) = parser.parse_args()

    commit(options.account, options.sequence, options.uri, options.start, options.end) 
