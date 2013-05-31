'''Puts Mongo id in MySQL utility bill rows.'''
from sys import stderr
import MySQLdb
import pymongo
from billing.util.dateutils import date_to_datetime

con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
con.autocommit(False)
cur = con.cursor()
db = pymongo.Connection('localhost')['skyline-dev']

cur.execute("begin")

# add column for mongo document id to utilbill table
# note that MySQL inserts its own default value for a new not-null column based
# on the type (for a string, it's "").
cur.execute("alter table utilbill add column document_id varchar(24) not null")

cur.execute("select utilbill.id, customer.account, service, period_start, period_end from utilbill join customer where utilbill.customer_id = customer.id")
for mysql_id, account, service, start, end in cur.fetchall():
    # get mongo id of editable utility bill document
    query = {
        'account': account,
        #'service': service,
        'start': date_to_datetime(start),
        'end': date_to_datetime(end),
        'sequence': {'$exists': False},
        'version': {'$exists': False},
    }
    mongo_doc = db.utilbills.find_one(query)
    if mongo_doc is None:
        print >> stderr, "%s: no mongo document for query %s" % (mysql_id, query)
        continue

    # put mongo document id in MySQL table
    cur.execute("update utilbill set document_id = '%s' where id = %s" % (mongo_doc['_id'], mysql_id))

    print "%s: success" % mysql_id

# check for success; abort if any rows did not get a document id
cur.execute("select count(*) from utilbill where document_id = ''")
count = cur.fetchone()[0]
if count > 0:
    #raise Exception("%s rows did not match a document" % count)
    print >> stderr, "%s rows did not match a document" % count
    #cur.rollback()
# NOTE currently about 1/3 of utility bill rows did not match a document

con.commit()


#ids = set()
#
#cur = con.cursor()
#for doc in db.utilbills.find({'sequence': {'$exists': False}}):
#    # find MySQL id
#    query = '''select utilbill.id from utilbill join customer where utilbill.customer_id = customer.id and account = "%s" and service = "%s" and period_start = "%s" and period_end = "%s"''' % (doc['account'], doc['service'], doc['start'], doc['end'])
#    cur.execute(query)
#    result = cur.fetchone()
#    if result is None:
#        print "Couldn't find utilbill document for query %s" % query
#        continue
#    mysql_id = result[0]
#
#    print doc['_id']
#
#    # find reebill document
#    reebills = db.reebills.find({'utilbills.id': doc['_id']})
#    if reebills.count() == 0:
#        print "    No reebills with utility bill id %s" % doc['_id']
#    elif reebills.count() > 1:
#        print "    Multiple reebills (%s) with utility bill id %s" % (reebills.count(), doc['_id'])
#
#    # update reebill document if necessary
#    for reebill in reebills: # handle multiple reebills even though there should never be more than 1
#        for utilbill_subdoc in reebill['utilbills']:
#            if utilbill_subdoc['id'] == doc['_id']:
#                utilbill_subdoc['id'] = mysql_id
#                print "    Updated reebill ", reebill['_id']
#        #db.reebills.save(reebill)
#
#    # update utilbill document
#    doc['_id'] = mysql_id
#
#    #db.utilbills.save(doc)
#
## TODO what id goes in attached/non-editable utility bills? arbitrary ObjectID or some combination of original MySQL id, account, sequence?
