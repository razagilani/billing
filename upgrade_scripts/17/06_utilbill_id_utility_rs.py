'''
Adds columns to utilbill table: document_id, utility, rate_class
Creates editable utility bill documents where they don't exist.
Fills document_id, utility, rate_class columns with _id, utility, rate_structure_name of editable utility bill document in Mongo.
'''
from sys import stderr
from operator import itemgetter
import MySQLdb
import pymongo
from pymongo import DESCENDING
from bson import ObjectId
from billing.util.dateutils import date_to_datetime
from billing.util.dictutils import subdict
from billing.util.mongo_utils import format_query

con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
con.autocommit(False)
cur = con.cursor()
db = pymongo.Connection('localhost')['skyline-dev']

def one(the_list):
    '''Ensure that 'the_list' has one element and return it.'''
    assert len(the_list) == 1
    return the_list[0]

def generate_utilbill_doc(account, start, end):
    '''Returns a new editable utility bill document for 'account' having the
    given dates, based on the most recent one for the 'account'. Raises
    StopIteration if none was found.'''
    result = next(db.utilbills.find({'account': account})\
            .sort([('start', DESCENDING), ('end', DESCENDING)]))
    result.update({ '_id': ObjectId(), 'start': date_to_datetime(start),
            'end': date_to_datetime(end)})
    result.pop('sequence', None)
    result.pop('version', None)
    return result

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

# put Mongo _ids, document_id, rate class of editable utility bill documents in MySQL
utilbill_query = '''
select utilbill.id, customer.account, period_start, period_end
from utilbill join customer on utilbill.customer_id = customer.id
order by account, period_start, period_end'''
cur.execute(utilbill_query)
for mysql_id, account, start, end in cur.fetchall():
    # get mongo id of editable utility bill document
    editable_doc_query = {
        'account': account,
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

        reebill_query = '''select sequence, version
        from reebill join utilbill_reebill on reebill_id = reebill.id
        and utilbill_id = %s
        order by sequence, version''' % mysql_id
        cur.execute(reebill_query)

        if cur.rowcount == 0:
            # this utility bill has no reebills, so it won't have a document
            # yet. create one by duplicating the newest utility bill for this
            # account that can be found
            mongo_doc = generate_utilbill_doc(account, start, end)
            db.utilbills.insert(mongo_doc)

            print ('INFO generated new document for unattached '
                    'utility bill: %s %s - %s') % (account, start, end)
        else:
            # this utility bill does have a reebill. the frozen utility bill
            # document belonging to that reebill can help find a document for
            # this utility bill.
            sequence, version = cur.fetchone()
            reebill_doc = db.reebills.find_one({'_id.account': account,
                    '_id.sequence': sequence, '_id.version': version})
            try:
                mongo_id = one(reebill_doc['utilbills'])['id']
            except AssertionError:
                print >> stderr, ("WARNING reebill %s-%s-%s has muiltiple "
                        "utility bills: couldn't be used to find editable "
                        "version of frozen utility bill document") % (account,
                        sequence, version)
                continue
            frozen_doc = db.utilbills.find_one({'_id': ObjectId(mongo_id)})
            if frozen_doc is None:
                print >> stderr, ('ERROR could not find document for utility '
                        'bill %s %s - %s and could not find frozen document '
                        'for reebill %s-%s') % (account, start, end, sequence,
                        version)
                continue

            editable_doc_query.update({'start': frozen_doc['start'],
                    'end': frozen_doc['end']})
            mongo_doc = db.utilbills.find_one(editable_doc_query)
            if mongo_doc is None:
                print >> stderr, ('ERROR could not find document for utility '
                        'bill %s %s - %s, and frozen document '
                        'for reebill %s-%s did not help') % (account, start,
                        end, sequence, version)
                continue
            print ('INFO used reebill %s-%s-%s to find editable utility bill'
                    ' document %s - %s') % (account, sequence, version,
                    frozen_doc['start'], frozen_doc['end'])

    # put mongo document id in MySQL table
    utilbill_update = ('''update utilbill set utility = '{utility}',
    rate_class = '{rate_structure_binding}', document_id = '{_id}'
    where id = %s''' %  mysql_id).format(**mongo_doc)
    cur.execute(utilbill_update)

# check for success; abort if any rows did not get a document id
cur.execute("select count(*) from utilbill where document_id in ('', NULL)")
count = cur.fetchone()[0]
if count > 0:
    print >> stderr, "%s rows did not match a document" % count
    #cur.rollback()


# insert mongo document ids in document_id column of utilbill_reebill to represent frozen utility bill documents
utilbill_reebill_query = '''
select reebill.id, customer.account, reebill.sequence, reebill.version
from reebill join customer on reebill.customer_id = customer.id'''
cur.execute(utilbill_reebill_query)
for mysql_id, account, sequence, version, in cur.fetchall():
    # get mongo id of editable utility bill document
    query = {
        '_id.account': account,
        '_id.sequence': sequence,
        '_id.version': version
    }
    reebill_doc = db.reebills.find_one(query)
    if reebill_doc is None:
        print >> stderr, "%s: no reebill document for query %s" % (mysql_id,
                query)
        continue
    try:
        assert len(reebill_doc['utilbills']) == 1
    except KeyError as e:
        print >> stderr, 'Reebill %s-%s-%s lacks "utilbills" key' % (account,
                sequence, version)
        continue
    except AssertionError as e:
        # TODO handle multi-utilbill cases (10001)
        if len(reebill_doc['utilbills']) == 0:
            print >> stderr, ('Reebill %s-%s-%s lacks utility bill '
                    'subdocuments') % (account, sequence, version)
            continue
        elif len(reebill_doc['utilbills']) > 1:
            print >> stderr, ('Reebill %s-%s-%s has multiple utility bill '
                    'subdocuments') % (account, sequence, version)
            continue
        else:
            raise
    utilbill_subdoc = reebill_doc['utilbills'][0]
    mongo_utilbill_id = utilbill_subdoc['id']

    # put mongo document id in MySQL table
    cur.execute(("update utilbill_reebill set document_id = '%s' "
            "where reebill_id = %s") % (mongo_utilbill_id, mysql_id))

# check for success; complain if any rows did not get a document id
cur.execute("select count(*) from utilbill where document_id is NULL")
count = cur.fetchone()[0]
cur.execute("select count(*) from utilbill")
total = cur.fetchone()[0]
if count > 0:
    print >> stderr, "%s of %s rows did not match a document" % (count, total)
    #cur.rollback()

con.commit()

