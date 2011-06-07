#!/usr/bin/python
"""
Utility functions to interact with state database
"""

import os, sys
import MySQLdb


from optparse import OptionParser


def fetch(host, db, user, password, query, params, fetchall = True):
    try:
        conn = MySQLdb.connect(host=host, user=user, passwd=password, db=db)

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

def commit_bill(host, db, user, password, account, sequence, start, end):

    query = "call commit_bill(%s, %s, %s, %s)"
    params = (account, sequence, start, end)
    return fetch(host, db, user, password, query, params, False)

def discount_rate(host, db, user, password, account):

    query = "select discountrate from customer where account = %s"
    params = (account)
    rows = fetch(host, db, user, password, query, params)
    # TODO: error checking...
    return rows[0]['discountrate']

def last_sequence(host, db, user, password, account):
    query = "select max(sequence) as maxseq from rebill where customer_id = (select id from customer where account = %s)"
    params = (account)
    rows = fetch(host, db, user, password, query, params)
    # TODO: error checking...
    return rows[0]['maxseq']

def issue(host, db, user, password, account, sequence):
    query = "update rebill set issued = 1 where sequence = %s and customer_id = (select id from customer where account = %s)"
    print query
    print "%s %s" % (sequence,account)
    params = (sequence, account)
    # TODO: error checking...
    rows = fetch(host, db, user, password, query, params, False)
    print str(rows)

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

