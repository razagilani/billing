from sys import stderr
import MySQLdb
import pymongo

con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
db = pymongo.Connection('localhost')['skyline-dev']

ids = set()

# put MySQL id in editable utility bill documents
cur = con.cursor()
for doc in db.utilbills.find({'sequence': {'$exists': False}}):
    # find MySQL id
    query = '''select utilbill.id from utilbill join customer where utilbill.customer_id = customer.id and account = "%s" and service = "%s" and period_start = "%s" and period_end = "%s"''' % (doc['account'], doc['service'], doc['start'], doc['end'])
    cur.execute(query)
    result = cur.fetchone()
    if result is None:
        print "Couldn't find utilbill document for query %s" % query
        continue
    mysql_id = result[0]

    print doc['_id']

    # find reebill document
    reebills = db.reebills.find({'utilbills.id': doc['_id']})
    if reebills.count() == 0:
        print "    No reebills with utility bill id %s" % doc['_id']
    elif reebills.count() > 1:
        print "    Multiple reebills (%s) with utility bill id %s" % (reebills.count(), doc['_id'])

    # update reebill document if necessary
    for reebill in reebills: # handle multiple reebills even though there should never be more than 1
        for utilbill_subdoc in reebill['utilbills']:
            if utilbill_subdoc['id'] == doc['_id']:
                utilbill_subdoc['id'] = mysql_id
                print "    Updated reebill ", reebill['_id']
        #db.reebills.save(reebill)

    # update utilbill document
    doc['_id'] = mysql_id

    #db.utilbills.save(doc)

# TODO what id goes in attached/non-editable utility bills? arbitrary ObjectID or some combination of original MySQL id, account, sequence?
