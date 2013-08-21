'''Puts Mongo id, utility name, and rate class in MySQL utility bill rows.'''
from sys import stderr
from operator import itemgetter
import MySQLdb
import pymongo
from billing.util.dateutils import date_to_datetime
from billing.util.dictutils import subdict

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

    # if there's no editable utility bill document, create one by copying the
    # highest-version frozen document
    if mongo_doc is None:
        any_doc_query = subdict(editable_doc_query, ['sequence', 'version'], invert=True)
        docs = db.utilbills.find(any_doc_query)
        if docs.count() == 0:
            print >> stderr, "No utility bills found for query", any_doc_query
            continue

        mongo_doc = max(docs, key=itemgetter('version'))
        del mongo_doc['sequence']; del mongo_doc['version']
        db.utilbills.save(mongo_doc)
        print >> stderr, "created editable document for utility bill", mysql_id

    # put mongo document id in MySQL table
    cur.execute("update utilbill set utility = '%s', rate_class = '%s', document_id = '%s' where id = %s" % (mongo_doc['utility'], mongo_doc['rate_structure_binding'], mongo_doc['_id'], mysql_id))

# check for success; abort if any rows did not get a document id
cur.execute("select count(*) from utilbill where document_id = ''")
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

# check for success; abort if any rows did not get a document id
cur.execute("select count(*) from utilbill where document_id = ''")
count = cur.fetchone()[0]
if count > 0:
    #raise Exception("%s rows did not match a document" % count)
    print >> stderr, "%s rows did not match a document" % count
    #cur.rollback()
# NOTE currently about 1/3 of utility bill rows did not match a document

con.commit()

