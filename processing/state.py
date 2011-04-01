#!/usr/bin/python
"""
Utility functions to interact with state database
"""

import os, sys
import MySQLdb


from optparse import OptionParser


def commit_bill(user, password, account, sequence, uri, start, end):

    try:
        conn = MySQLdb.connect(host="tyrell", user=user, passwd=password, db="skyline")

        commit_bill = "call commit_bill(%s, %s, %s, %s, %s)"

        cur = conn.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(commit_bill, (account, sequence, uri, start, end))
        # TODO: print some sane message about failures
        print cur.fetchall()
        #print "Number of rows inserted: %d" % cur.rowcount
        conn.commit()
        cur.close()

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


if __name__ == "__main__":

    parser = OptionParser()

    parser.add_option("--account", dest="account", help="Customer billing account")
    parser.add_option("--sequence", dest="sequence", help="Bill sequence number")
    parser.add_option("--uri", dest="uri", help="The location of the bill")
    parser.add_option("--start", dest="start", help="RE bill period start")
    parser.add_option("--end", dest="end", help="RE bill period end")

    (options, args) = parser.parse_args()

    commit(options.account, options.sequence, options.uri, options.start, options.end) 
