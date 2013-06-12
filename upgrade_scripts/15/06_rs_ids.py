'''Puts Mongo id in MySQL utility bill rows.'''
from sys import stderr
import MySQLdb
import pymongo
from billing.util.dateutils import date_to_datetime
from bson import ObjectId

con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
con.autocommit(False)
cur = con.cursor()
db = pymongo.Connection('localhost')['skyline-dev']

# add foreign key columns to utilbill table (but don't make them "not null" yet,
# because insertion of default values violates the foreign key constraint)
cur.execute("""alter table utilbill add column uprs_document_id varchar(24) not null""")
cur.execute("""alter table utilbill add column cprs_document_id varchar(24) not null""")

cur.execute("begin")

cur.execute("select customer.account, reebill.sequence, reebill.version, utilbill_id from reebill join customer join utilbill_reebill where reebill.customer_id = customer.id and reebill.id = utilbill_reebill.reebill_id")
for account, sequence, version, utilbill_id in cur.fetchall():
    print account, sequence, version, utilbill_id
    # find CPRS and UPRS docs
    cprs_query = {
        '_id.type': 'CPRS', 
        '_id.account': account,
        '_id.sequence': sequence,
        '_id.version': version
    }
    cprss = db.ratestructure.find(cprs_query)
    if cprss.count() == 0:
        print >> stderr, "Missing CPRS:", cprs_query
        continue
    elif cprss.count() > 1:
        print >> stderr, "Multiple CPRSs match", cprs_query
        continue
    cprs = cprss[0]
    uprs_query = {
        '_id.type': 'UPRS', 
        '_id.account': account,
        '_id.sequence': sequence,
        '_id.version': version
    }
    uprss = db.ratestructure.find(uprs_query)
    if uprss.count() == 0:
        print >> stderr, "Missing UPRS:", uprs_query
        continue
    elif uprss.count() > 1:
        print >> stderr, "Multiple UPRSs match", uprs_query
        continue
    uprs = uprss[0]

    # delete CPRS and UPRS docs from collection
    # TODO do this after saving replacement, not before
    db.ratestructure.remove(cprs)
    db.ratestructure.remove(uprs)

    # replace ids with new ones, and add "type" field to the body of the document
    cprs['_id'] = ObjectId()
    uprs['_id'] = ObjectId()
    cprs['type'] = 'CPRS'
    uprs['type'] = 'UPRS'

    cur.execute("update utilbill set cprs_document_id = '%s' where id = %s" %
            (cprs['_id'], utilbill_id))
    cur.execute("update utilbill set uprs_document_id = '%s' where id = %s" %
            (uprs['_id'], utilbill_id))

    db.ratestructure.save(cprs)
    db.ratestructure.save(uprs)

con.commit()

# TODO enable after verifying that every utilbill gets a cprs_document_id and uprs_document_id
#cur.execute("alter table utilbill modify cprs_document_id integer not null")
#cur.execute("alter table utilbill modify uprs_document_id integer not null")


# TODO clean up remaining documents that have old-style id. are there any?

# TODO what to do with UPRS documents? probably move their RSIs into UPRS whenever they are not overridden.
