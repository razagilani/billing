'''This script creates frozen utility bill documents that should exist
according to the design of ReeBill 16 but do not, by copying editable documents
that are attached to issued reebills.'''
import MySQLdb
import pymongo
from bson import ObjectId

db = pymongo.Connection('localhost')['skyline-dev']
con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
con.autocommit(False)
cur = con.cursor()

query_for_issued_reebills = '''
select account, sequence, max_version
from rebill join customer on customer.id = customer_id
where issued = 1'''

cur.execute(query_for_issued_reebills)
for account, sequence, max_version in cur.fetchall():
    for version in range(max_version + 1):

        reebill_doc = db.reebills.find_one({'_id.account': account, '_id.sequence': sequence,
                '_id.version': version})
        for subdoc in reebill_doc['utilbills']:
            utilbill_doc = db.utilbills.find_one({'_id': subdoc['id']})

            if 'sequence' in utilbill_doc or 'version' in utilbill_doc:
                assert 'sequence' in utilbill_doc and 'version' in utilbill_doc
                continue
            
            utilbill_doc['sequence'] = sequence
            utilbill_doc['version'] = version
            utilbill_doc['_id'] = subdoc['id'] = ObjectId()

            db.utilbills.insert(utilbill_doc)
            db.reebills.save(reebill_doc)

            print 'fixed %s-%s-%s' % (account, sequence, version)


