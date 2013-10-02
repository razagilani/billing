'''
Adds columns to utilbill table: document_id, utility, rate_class
Creates editable utility bill documents where they don't exist.
Fills document_id, utility, rate_class columns with _id, utility, rate_structure_name of editable utility bill document in Mongo.
'''
from sys import stderr
from operator import itemgetter
import MySQLdb
import pymongo
from bson import ObjectId
from billing.util.dateutils import date_to_datetime
from billing.util.dictutils import subdict
from billing.util.mongo_utils import format_query

def one(the_list):
    #assert len(the_list) == 1
    if len(the_list) != 1:
        print >> stderr, type(the_list), 'has', len(the_list), 'elements'
    return the_list[0]

con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
con.autocommit(False)
cur = con.cursor()
db = pymongo.Connection('localhost')['skyline-dev']

cur.execute("begin")

# add column for mongo document id to utilbill table
# note that MySQL inserts its own default value for a new not-null column based
# on the type (for a string, it's "").
cur.execute("alter table utilbill add column utility varchar(45) not null")
cur.execute("alter table utilbill add column rate_class varchar(45) not null")
cur.execute("alter table utilbill add column document_id varchar(24)")

# also add document_id column to utilbill_reebill table: Mongo utility bill id,
# null if reebill is unissued because its mongo doc is the "current" one
# identified by utilbill.document_id
cur.execute("alter table utilbill_reebill add column document_id varchar(24)")

## create a new editable utility bill document from the hightest-version frozen
## document for each reebill
#cur.execute("select distinct customer.account, sequence from customer, reebill where reebill.customer_id = customer.id order by account, sequence")
#for account, sequence in cur.fetchall():
    #frozen_doc_query = {
        #'account': account,
        #'sequence': sequence,
    #}
    #docs = db.utilbills.find(frozen_doc_query)
    #if docs.count() == 0:
        #print >> stderr, "No frozen utility bill document found for reebill %s-%s: %s" % (account, sequence, frozen_doc_query)
        #continue
    #new_editable_doc = max(docs, key=itemgetter('version'))
    #del new_editable_doc['sequence']
    #del new_editable_doc['version']
    #new_editable_doc['_id'] = ObjectId()
    #db.utilbills.save(new_editable_doc)

# put Mongo _ids, document_id, rate class of editable utility bill documents in MySQL
cur.execute("select utilbill.id, customer.account, service, period_start, period_end from utilbill join customer where utilbill.customer_id = customer.id")
for mysql_id, account, service, start, end in cur.fetchall():
    # get mongo id of editable utility bill document
    editable_doc_query = {
        'account': account,
        #'service': service,
        'start': date_to_datetime(start),
        'end': date_to_datetime(end),
        'sequence': {'$exists': False},
        'version': {'$exists': False},
    }
    mongo_doc = db.utilbills.find_one(editable_doc_query)

    # if there's no editable utility bill document matching the date fields in
    # MySQL, but there is a reebill associated with this utility bill, find the
    # reebill, look up its utility bill document, try to find an editable
    # utility bill with the same dates as that one, and put that one's _id in MySQL
    if mongo_doc is None:
        #print >> stderr, "No editable utility bill document found for query", editable_doc_query

        cur.execute("select sequence, version from reebill, utilbill_reebill where reebill_id = reebill.id and utilbill_id = %s" % mysql_id)
        if cur.rowcount == 0:
            print >> stderr, ("No editable utility bill document found for "
                    "query %s and no reebill exists in MySQL") % \
                    format_query(editable_doc_query)
            continue

        sequence, version = cur.fetchone()
        mongo_id = one(db.reebills.find_one({'_id.account': account, '_id.sequence': sequence, '_id.version': version})['utilbills'])['id']
        frozen_doc = db.utilbills.find_one({'_id': ObjectId(mongo_id)})
        if frozen_doc is None:
            print >> stderr, "and reebill's utility bill document could not be found either"
            continue

        editable_doc_query.update({'start': frozen_doc['start'], 'end': frozen_doc['end']})
        mongo_doc = db.utilbills.find_one(editable_doc_query)
        if mongo_doc is None:
            print >> stderr, "and no utility bill matching the dates of the reebill's frozen utility bill document could be found"
            continue

    # put mongo document id in MySQL table
    cur.execute("update utilbill set utility = '%s', rate_class = '%s', document_id = '%s' where id = %s" % (mongo_doc['utility'], mongo_doc['rate_structure_binding'], mongo_doc['_id'], mysql_id))

# check for success; abort if any rows did not get a document id
cur.execute("select count(*) from utilbill where document_id in ('', NULL)")
count = cur.fetchone()[0]
if count > 0:
    #raise Exception("%s rows did not match a document" % count)
    print >> stderr, "%s rows did not match a document" % count
    #cur.rollback()
# NOTE currently about 1/3 of utility bill rows did not match a document


# insert mongo document ids in document_id column of utilbill_reebill to represent frozen utility bill documents
cur.execute("select reebill.id, customer.account, reebill.sequence, reebill.version from reebill join customer where reebill.customer_id = customer.id")
for mysql_id, account, sequence, version, in cur.fetchall():
    # get mongo id of editable utility bill document
    query = {
        '_id.account': account,
        '_id.sequence': sequence,
        '_id.version': version
    }
    reebill_doc = db.reebills.find_one(query)
    if reebill_doc is None:
        print >> stderr, "%s: no reebill document for query %s" % (mysql_id, query)
        continue
    try:
        assert len(reebill_doc['utilbills']) == 1
    except KeyError as e:
        print >> stderr, 'Reebill %s-%s-%s lacks "utilbills" key' % (account, sequence, version)
        continue
    except AssertionError as e:
        # TODO handle multi-utilbill cases (10001)
        if len(reebill_doc['utilbills']) == 0:
            print >> stderr, 'Reebill %s-%s-%s lacks utility bill subdocuments' % (account, sequence, version)
            continue
        elif len(reebill_doc['utilbills']) > 1:
            print >> stderr, 'Reebill %s-%s-%s has multiple utility bill subdocuments' % (account, sequence, version)
            continue
        else:
            raise
    utilbill_subdoc = reebill_doc['utilbills'][0]
    mongo_utilbill_id = utilbill_subdoc['id']

    # put mongo document id in MySQL table
    cur.execute("update utilbill_reebill set document_id = '%s' where reebill_id = %s" % (mongo_utilbill_id, mysql_id))

# check for success; complain if any rows did not get a document id
cur.execute("select count(*) from utilbill where document_id is NULL")
count = cur.fetchone()[0]
cur.execute("select count(*) from utilbill")
total = cur.fetchone()[0]
if count > 0:
    print >> stderr, "%s of %s utilbill rows did not match a document" % (count, total)
    #raise Exception("%s rows did not match a document" % count)
    #cur.rollback()

con.commit()

