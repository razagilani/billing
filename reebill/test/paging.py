#!/usr/bin/python
import os
import sys
import MySQLdb
import billing.json_util as ju # better than the 'json' module for mapping python objects to JSON strings
import cherrypy
from cherrypy.lib import static

# cherrypy configuration
local_conf = {
    '/' : {
        'tools.staticdir.root' :os.path.dirname(os.path.abspath(__file__)), 
        'tools.staticdir.dir' : '',
        'tools.staticdir.on' : True,
        'tools.expires.secs': 0,
        'tools.response_headers.on': True,
    },
    '/js' :  {
        'tools.staticdir.dir' : 'js',
        'tools.staticdir.on' : True 
    },
}
cherrypy.config.update({
    'server.socket_port': 8080,
})
cherrypy.quickstart(Paging(), config=local_conf)

'''Cherrypy object to answer requests for utilbills table slices.'''
class Paging(object):
    @cherrypy.expose
    def getbills(self, start, limit, **args):
        # call getrows to actually query the database; return the result in
        # JSON format if it succeded or an error if it didn't
        try:
            result, totalCount = getrows(int(start), int(limit))
            return ju.dumps({'success': True, 'rows':result, 'results':totalCount})
        except Exception as e:
            print e
            return '{success: false}'
    
'''Queries the 'skyline_dev' database on tyrell for account, start date, and
end date of bills in a slice of the utilbills table; returns the slice and the
total number of rows in the table (for paging).'''
def getrows(start, limit):
    try:
        # connect to database
        conn = MySQLdb.connect(host='tyrell', user='dev', passwd='dev', \
                db='skyline_dev')
        
        # get appropriate slice of table
        cur = conn.cursor(MySQLdb.cursors.DictCursor)
        cur.execute('''select account, period_start, period_end 
                from customer, utilbill
                where customer.id = utilbill.customer_id
                limit %d,%d''' % (start, limit))
        theSlice = cur.fetchall()
        
        # count total number of rows in the whole table (not just the slice)
        cur.execute('''select count(*) as count from utilbill''')
        totalCount = int(cur.fetchone()['count'])
        
        # return the slice (dictionary) and the overall count (integer)
        return theSlice, totalCount
    except MySQLdb.Error:
        # TODO is this kind of error checking good enough?
        print "Database error"
        raise
    except:
        print "Unexpected error:", sys.exc_info()[0]
        raise
    finally:
        conn.close()


