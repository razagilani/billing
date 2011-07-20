#!/usr/bin/python
'''
Description: Produces a variety of reports describing the processing status of billing
'''

import os, sys
import jinja2
import MySQLdb


from optparse import OptionParser


def main():

    queries = {
            "last_processed" : "select c.account, c.name, max(u.period_start) as period_start, max(u.period_end) as period_end from utilbill u left join rebill r on u.rebill_id = r.id, customer c where u.customer_id = c.id and u.rebill_id is not null group by c.name order by c.account",
            "unprocessed" : "select customer.account, customer.name, utilbill.period_start, utilbill.period_end from customer, utilbill where customer.id = utilbill.customer_id and received = 1 and processed = 0 order by account, period_start, received desc",
            "missing" : "select customer.account, customer.name, utilbill.period_start, utilbill.period_end from customer, utilbill where customer.id = utilbill.customer_id and received = 0 order by account, period_start, received desc",
            "unbilled" : "select c.account, c.name from customer c left join utilbill ub on ub.customer_id = c.id where customer_id is NULL",
            "dayssince" : "select c.account, c.name, datediff(curdate(), max(u.period_end)) as dayssince from utilbill u left join rebill r on u.rebill_id = r.id, customer c where u.customer_id = c.id and u.rebill_id is not null group by c.name order by c.account"
        }

    template_values = {}

    try:
        # TODO: remove password string
        db_conn = MySQLdb.connect(host="tyrell", user="prod", passwd="JCnvgUOTxHzEasKUBNv3", db="skyline")

        for name, query in queries.iteritems():
            cur = db_conn.cursor(MySQLdb.cursors.DictCursor)
            result = cur.execute(query)
            template_values[name] = cur.fetchall()
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

        if (vars().has_key('db_conn') is True and type(db_conn) is MySQLdb.connections.Connection): 
            db_conn.close()

    env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
            )

    template = env.get_template("status_text.jnj") 
                        
    with file(os.path.join("", "status_text.txt"), 'w') as out:
        out.writelines(template.render(template_values))


if __name__ == "__main__":
    # configure optparse
    parser = OptionParser()

    (options, args) = parser.parse_args()

    main() 
