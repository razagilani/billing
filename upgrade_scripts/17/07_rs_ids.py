'''Puts Mongo id in MySQL utility bill rows.'''
from sys import stderr
import MySQLdb
import pymongo
from billing.util.dateutils import date_to_datetime
from billing.util.mongo_utils import check_error, format_query
from bson import ObjectId

con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
con.autocommit(False)
cur = con.cursor()
db = pymongo.Connection('localhost')['skyline-dev']

# add foreign key columns to utilbill table (but don't make them "not null" yet,
# because insertion of default values violates the foreign key constraint)
cur.execute("""alter table utilbill add column uprs_document_id varchar(24)""")
cur.execute("""alter table utilbill add column cprs_document_id varchar(24)""")
cur.execute("""alter table customer add column utilbill_template_id varchar(24) not null""")

# also add uprs_id and cprs_id to utilbill_reebill table
cur.execute("""alter table utilbill_reebill add column uprs_document_id varchar(24)""")
cur.execute("""alter table utilbill_reebill add column cprs_document_id varchar(24)""")

cur.execute("begin")

#reebill_query = '''
#select reebill.id, customer.account, reebill.sequence, reebill.version, reebill.issued, utilbill_id
#from reebill join customer join utilbill_reebill
#where reebill.customer_id = customer.id
#and reebill.id = utilbill_reebill.reebill_id'''
reebill_query = '''
select reebill.id, customer.account, reebill.sequence, reebill.version, reebill.issued, utilbill_id
from reebill join customer join utilbill_reebill
where reebill.customer_id = customer.id
and reebill.id = utilbill_reebill.reebill_id'''
cur.execute(reebill_query)
initial_count = db.ratestructure.count()

# this set tracks queries for CPRS documents to delete. because some reebills
# have multiple utility bills (in MySQL) and CPRS documents are identified by
# reebill sequence/version, there are effectively multiple utility bills
# sharing the same CPRS documents. therefore CPRS documents can't be deleted
# until all utilbill_reebill rows that involve them have been processed. note
# that in the case of a reebill having multiple utility bills, the number of
# CPRS documents will increase by [number of utility bills] - 1. a set is used
# because duplicate queries will result in deletion failure after the first.
# see https://www.pivotaltracker.com/story/show/58115570
deletes = set()

# count duplicate occurrences of the same reebill in the loop. whenever a
# reebill occurs more than once, it has multiple utility bills all sharing the
# same RS documents, and 2 new RS documents will be added. the total number of
# RS documents should only have increases by the number of these duplicates.
duplicate_count = 0
last_reebill_id = None

for reebill_id, account, sequence, version, issued, utilbill_id in cur.fetchall():

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
        print >> stderr, "Missing UPRS:", format_query(uprs_query)
        continue
    elif uprss.count() > 1:
        print >> stderr, "Multiple UPRSs match", format_query(uprs_query)
        continue
    uprs = uprss[0]

    # deletion of old CPRS and UPRS docs is deferred until the end of the loop.
    # query dict is "encoded" as frozenset of key-value pairs because only
    # hashable (i.e. immutable) objects can be stored in a set
    deletes.add(frozenset(uprs_query.items()))
    deletes.add(frozenset(cprs_query.items()))

    # replace ids with new ones, and add "type" field to the body of the document
    cprs['_id'] = ObjectId()
    uprs['_id'] = ObjectId()
    cprs['type'] = 'CPRS'
    uprs['type'] = 'UPRS'

    cur.execute("update utilbill set cprs_document_id = '%s' where id = %s" %
            (cprs['_id'], utilbill_id))
    cur.execute("update utilbill set uprs_document_id = '%s' where id = %s" %
            (uprs['_id'], utilbill_id))

    # put RS document ids in utilbill_reebill table only if the reebill is
    # issued
    if issued:
        cur.execute(("update utilbill_reebill set uprs_document_id = '%s', " "cprs_document_id = '%s' where reebill_id = %s" " and utilbill_id = %s") % (uprs['_id'], cprs['_id'], reebill_id, utilbill_id))

    db.ratestructure.insert(cprs)
    db.ratestructure.insert(uprs)

    if reebill_id == last_reebill_id:
        duplicate_count += 1
    last_reebill_id = reebill_id

# delete all documents in 'deletes'
for kvp_set in deletes:
    # frozenset of key-value pairs needs to be "decoded" into a dict
    query = dict(kvp_set)
    check_error(db.ratestructure.remove(query, safe=True))

# total number of rate structure documents should not have changed, except when
# there were reebills sharing the same RS documents, in which case one CPRS and
# one UPRS is added
try:
    assert db.ratestructure.count() == initial_count + 2 * duplicate_count
except AssertionError:
    import ipdb; ipdb.set_trace()

# put ids of "template" utility bills in MySQL customer table
cur.execute("select account, customer.id from customer order by account")
for account, customer_id in cur.fetchall():
    cur.execute("select count(*) from reebill where customer_id = '%s' and issued = 1" % customer_id)
    num_reebills = cur.fetchone()[0]

    #print 'template for %s (%s reebills issued)' % (account, num_reebills)

    # find utilbill, CPRS and UPRS docs
    utilbill_query = {
        'account': account,
        'sequence': 0
    }
    utilbills = db.utilbills.find(utilbill_query)
    if utilbills.count() == 0:
        if num_reebills == 0:
            print >> stderr, "ERROR missing template utility bill:", format_query(utilbill_query)
        else:
            print >> stderr, "WARNING missing template utility bill: %s (unnecessary since bills have been issued)" % format_query(utilbill_query)
        continue
    if utilbills.count() > 1:
        print >> stderr, "ERROR multiple documents match query for template utility bill", format_query(utilbill_query)
        continue
    utilbill = utilbills[0]

    command = """update customer set
            utilbill_template_id = '{utilbill_template_id}'
            where id = '{customer_id}'""".format(
            utilbill_template_id=str(utilbill['_id']),
            customer_id=customer_id)
    cur.execute(command)

con.commit()

# TODO make new columns not null after verifying that every value is filled in?
#cur.execute("alter table utilbill modify cprs_document_id integer not null")
#cur.execute("alter table utilbill modify uprs_document_id integer not null")


# TODO clean up remaining documents that have old-style id. are there any?

# TODO what to do with UPRS documents? probably move their RSIs into UPRS whenever they are not overridden.
