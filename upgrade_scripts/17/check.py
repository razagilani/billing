'''
Check facts about the databases that should be true after all upgrade scripts have been run.
see https://www.pivotaltracker.com/story/show/55042588
'''
from sys import stderr
import pymongo
from bson import ObjectId
from MySQLdb import Connection

con = Connection('localhost', 'dev', 'dev', 'skyline_dev')
cur = con.cursor()
db = pymongo.Connection('localhost')['skyline-dev']

cur.execute("select count(*) from utilbill")
count = cur.fetchall()[0]
print '%s total rows in utilbill' % count

# all non-hypothetical utility bills should have 3 documents filled in
cur.execute("select count(*) from utilbill where state < 3 and document_id is null or uprs_document_id is null or cprs_document_id is null")
count = cur.fetchall()[0]
if count > 0:
    print >> stderr, '%s rows in utilbill have null documents but state < 3' % count

# all non-hypothetical utility bills should have 0 documents filled in
cur.execute("select count(*) from utilbill where state = 3 and document_id is not null or uprs_document_id is not null or cprs_document_id is not null")
count = cur.fetchall()[0]
if count > 0:
    print >> stderr, '%s rows in utilbill have documents but state = 3' % count

# all issued reebills should have a frozen utility bill document
cur.execute("select count(*) from utilbill_reebill, reebill where reebill_id = reebill.id and issued = 1 and (document_id is null or uprs_document_id is null or cprs_document_id is null)")
count = cur.fetchall()[0]
if count > 0:
    print >> stderr, '%s issued reebills lack frozen utility bill documents' % count

# no unissued reebills should have a frozen utility bill document
cur.execute("select count(*) from utilbill_reebill, reebill where reebill_id = reebill.id and issued = 0 and (document_id is not null or uprs_document_id is not null or cprs_document_id is not null)")
count = cur.fetchall()[0]
if count > 0:
    print >> stderr, '%s unissued reebills have frozen utility bill documents' % count

# there should be no duplicate document ids in the union of document_id, uprs_id, cprs_id in utilbill and utilbill_reebill
for id_type in ('document_id', 'uprs_document_id', 'cprs_document_id'):
    cur.execute("select count(*) from ((select %(id_type)s from utilbill) union all (select %(id_type)s from utilbill_reebill as a)) as t" % {'id_type': id_type})
    total_count = cur.fetchone()[0]
    cur.execute("select count(*) from ((select %(id_type)s from utilbill) union distinct (select %(id_type)s from utilbill_reebill as a)) as t" % {'id_type': id_type})
    distinct_count = cur.fetchone()[0]
    duplicates = total_count - distinct_count
    if duplicates > 0:
        print >> stderr, '%s duplicate %ss' % (duplicates, id_type)

# every mongo document referenced by an id in mysql should exist
cur.execute("(select document_id, uprs_document_id, cprs_document_id from utilbill) union distinct (select document_id, uprs_document_id, cprs_document_id from utilbill_reebill)")
for document_id, uprs_id, cprs_id in cur.fetchall():
    utilbill = db.utilbills.find_one({'_id': ObjectId(document_id)})
    uprs = db.ratestructure.find_one({'_id': ObjectId(uprs_id)})
    cprs = db.ratestructure.find_one({'_id': ObjectId(cprs_id)})
    if utilbill is None:
        print >> stderr, "couldn't load utility bill with _id %s" % document_id
    if uprs is None:
        print >> stderr, "couldn't load UPRS with _id %s" % uprs_id
    if cprs is None:
        print >> stderr, "couldn't load CPRS with _id %s" % cprs_id

# in reebill table, for every row having customer_id c, sequence s, version v > 0, there is another row with customer_id c, sequence s, version v - 1
cur.execute("select customer_id, sequence, version from reebill where version > 0")
for customer_id, sequence, version in cur.fetchall():
    cur.execute("select count(*) from reebill where customer_id = %s and sequence = %s and version = %s" % (customer_id, sequence, version - 1))
    count = cur.fetchone()[0]
    if count < 1:
        print >> stderr, 'missing version %s for reebill %s-%s' % (version - 1, customer_id, sequence)
    elif count > 1:
        print >> stderr, '%s reebills for %s-%s-%s' % (count, customer_id, sequence, version)
    
# all reebill documents referenced by account, sequence, version should exist in mongo
cur.execute("select account, sequence, version from reebill, customer where customer_id = customer.id")
for account, sequence, version in cur.fetchall():
    query = {'_id.account': account, '_id.sequence': sequence, '_id.version': version}
    doc = db.reebills.find_one({'_id.account': account, '_id.sequence': sequence, '_id.version': version})
    if doc is None:
        print >> stderr, "couldn't load reebill: %s" % query
