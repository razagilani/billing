'''
Check facts about the databases that should be true after all upgrade scripts have been run.
see https://www.pivotaltracker.com/story/show/55042588
'''
from sys import stderr
from bisect import bisect_left
import pymongo
from bson import ObjectId
from MySQLdb import Connection

con = Connection('localhost', 'dev', 'dev', 'skyline_dev')
cur = con.cursor()
db = pymongo.Connection('localhost')['skyline-dev']

cur.execute("select count(*) from utilbill")
count = cur.fetchall()[0]
print '%s total rows in utilbill' % count

# all utility bills should have service, utility, rate class filled in
cur.execute("select count(*) from utilbill where service is null or service = ''")
count = cur.fetchall()[0]
if count > 0:
    print >> stderr, '%s rows in utilbill have null/empty service' % count
cur.execute("select count(*) from utilbill where utility is null or utility = ''")
count = cur.fetchall()[0]
if count > 0:
    print >> stderr, '%s rows in utilbill have null/empty utility' % count
cur.execute("select count(*) from utilbill where rate_class is null or rate_class = ''")
count = cur.fetchall()[0]
if count > 0:
    print >> stderr, '%s rows in utilbill have null/empty rate_class' % count

# all non-hypothetical utility bills should have 3 documents filled in
cur.execute("select count(*) from utilbill where state < 3 and (document_id is null or uprs_document_id is null or cprs_document_id is null)")
count = cur.fetchall()[0]
if count > 0:
    print >> stderr, '%s rows in utilbill have null documents but state < 3' % count

# all non-hypothetical utility bills should have 0 documents filled in
cur.execute("select count(*) from utilbill where state = 3 and (document_id is not null or uprs_document_id is not null or cprs_document_id is not null)")
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
    cur.execute("select count(*) from ((select %(id_type)s from utilbill where %(id_type)s is not null) union all (select %(id_type)s from utilbill_reebill as a where %(id_type)s is not null)) as t" % {'id_type': id_type})
    total_count = cur.fetchone()[0]
    cur.execute("select count(*) from ((select %(id_type)s from utilbill where %(id_type)s is not null) union distinct (select %(id_type)s from utilbill_reebill as a where %(id_type)s is not null)) as t" % {'id_type': id_type})
    distinct_count = cur.fetchone()[0]
    duplicates = total_count - distinct_count
    if duplicates > 0:
        print >> stderr, '%s of %s non-null %ss have duplicates' % (duplicates, total_count, id_type)

# every mongo document referenced by an id in mysql should exist
cur.execute("(select document_id, uprs_document_id, cprs_document_id from utilbill) union distinct (select document_id, uprs_document_id, cprs_document_id from utilbill_reebill)")
doc_count, uprs_count, cprs_count = 0, 0, 0
for document_id, uprs_id, cprs_id in cur.fetchall():
    if document_id is not None:
        utilbill = db.utilbills.find_one({'_id': ObjectId(document_id)})
        if utilbill is None:
            #print >> stderr, "couldn't load utility bill with _id %s" % document_id
            doc_count += 1
    if uprs_id is not None:
        uprs = db.ratestructure.find_one({'_id': ObjectId(uprs_id)})
        if uprs is None:
            #print >> stderr, "couldn't load UPRS with _id %s" % uprs_id
            uprs_count += 1
    if cprs_id is not None:
        cprs = db.ratestructure.find_one({'_id': ObjectId(cprs_id)})
        if cprs is None:
            #print >> stderr, "couldn't load CPRS with _id %s" % cprs_id
            cprs_count += 1
if doc_count + uprs_count + cprs_count > 0:
    print >> stderr, "%s document_ids, %s uprs_ids, %s cprs_ids couldn't be loaded" % (doc_count, uprs_count, cprs_count)

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

# count number of utility bill, UPRS, CPRS documents documents that are not
# referenced in Mongo (these are not probably harmful, just evidence of
# something else that went wrong, and they're clutter)
def count_orphaned_docs(mysql_column, mongo_collection, mongo_query):
    cur.execute("select %s from utilbill" % mysql_column)
    # binary search sorted list of ids from MySQL column for each Mongo _id
    # string
    mysql_ids = sorted(zip(*cur.fetchall())[0])
    mongo_ids = (str(doc['_id']) for doc in mongo_collection.find(mongo_query,
            {'_id':1}))
    orphaned_count, total_count = 0, 0
    for _id in mongo_ids:
        mysql_id_idx = bisect_left(mysql_ids, _id)
        if not mysql_ids[mysql_id_idx] == _id:
            orphaned_count += 1
        total_count += 1
    return orphaned_count, total_count
print '%s of %s utility bill documents are orphaned' % count_orphaned_docs(
        'document_id', db.utilbills, {})
print '%s of %s UPRS documents are orphaned' % count_orphaned_docs(
        'uprs_document_id', db.ratestructure, {'type': 'UPRS'})
print '%s of %s CPRS documents are orphaned' % count_orphaned_docs(
        'cprs_document_id', db.ratestructure, {'type': 'CPRS'})

# count rate structure documents with old-style _ids
count = db.ratestructure.find({'_id.account': {'$exists': True}}).count()
print '%s rate structure documents have old-style _ids' % count

# all utility bill documents referenced by document_id in utilbill should have
# "sequence"/"version" keys
count = 0
cur.execute("select document_id from utilbill")
for (document_id,) in cur.fetchall():
    if document_id is None:
        continue
    doc = db.utilbills.find_one({'_id': ObjectId(document_id)})
    if doc is None:
        continue
    if 'sequence' in doc or 'version' in doc:
        count += 1
print '%s editable utility bill documents have sequence/version keys' % count

# no utility bill documents referenced by document_id in utilbill_reebill
# should have "sequence"/"version" keys
count = 0
cur.execute("select document_id from utilbill_reebill")
for (document_id,) in cur.fetchall():
    if document_id is None:
        continue
    doc = db.utilbills.find_one({'_id': ObjectId(document_id)})
    if doc is None:
        continue
    if 'sequence' not in doc or 'version' not in doc:
        count += 1
print '%s frozen utility bill documents lack sequence/version keys' % count

# utility bill documents should have same account, start, ende, service,
# utility, rate_class as MySQL rows
count = 0
cur.execute('''
select account, period_start, period_end, service, utility, rate_class,
document_id
from utilbill join customer on customer_id = customer.id''')
for account, start, end, service, utility, rate_class, document_id in cur.fetchall():
    if document_id is None:
        continue
    doc = db.utilbills.find_one({'_id': ObjectId(document_id)})
    if doc is None:
        continue
    if doc['account'] != account or doc['start'] != start or doc['end'] != end\
            or doc['service'] != service or doc['utility'] != utility \
            or doc['rate_structure_binding'] != rate_class:
        count += 1
print '%s utility bill documents differ from MySQL row in at least one "metadata" key' % count

# all reebill versions below highest should be issued
cur.execute('''
select count(*) from reebill where
issued = 0 and (customer_id, sequence, version) not in (
    select customer_id, sequence, max(version)
    from reebill
    group by customer_id, sequence
    order by customer_id, sequence
)
''')
count = cur.fetchall()[0]
print '%s non-highest-version reebills are issued' % count

# utility bill ids in reebill mongo documents match the ones in MySQL
cur.execute('''
select account, sequence, version, issued, utilbill_reebill.document_id, utilbill.document_id
from customer join reebill on customer.id = customer_id
join utilbill_reebill on reebill.id = reebill_id
join utilbill on utilbill_id = utilbill.id''')
count = 0
for account, sequence, version, issued, frozen_document_id, editable_document_id in cur.fetchall():
    reebill_doc = db.reebills.find_one({'_id.account': account,
            '_id.sequence': sequence, '_id.version': version})
    id_to_look_for = frozen_document_id if issued else editable_document_id
    if ObjectId(id_to_look_for) not in (subdoc['id'] for subdoc in
            reebill_doc['utilbills']):
        count += 1
print '%s reebill document ids do not match MySQL document_id column' % count

# every reebill has a utility bill in MySQL
cur.execute('''select count(*) from
reebill left outer join utilbill_reebill on reebill_id = reebill.id
where utilbill_id is null''')
count = cur.fetchall()[0]
print '%s rows in reebill table do not match rows of utilbill' % count

# every utility bill has same customer_id as corresponding reebill
cur.execute('''select count(*)
from utilbill join utilbill_reebill on utilbill.id = utilbill_id
join reebill on reebill_id = reebill.id
where utilbill.customer_id != reebill.customer_id;
''')
count = cur.fetchall()[0]
print '%s non-matching customer_ids between corresponding reebill and utilbill rows' % count
