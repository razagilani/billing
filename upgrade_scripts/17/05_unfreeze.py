'''
Converts frozen utility bill documents associated with unissued version-0 reebills into editable ones, replacing any editable utility bills that already exist.
'''
from sys import stderr
import pymongo
from billing.util.dateutils import date_to_datetime
from bson import ObjectId
import MySQLdb
from billing.util.dictutils import subdict, dict_merge

db = pymongo.Connection('localhost')['skyline-dev']
con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
con.autocommit(False)

# remove all editable utility bill documents so that better ones can be
# recreated from the frozen ones
db.utilbills.remove({'sequence': {'$exists': False}})

# iterate through all unissued version-0 reebills
cur = con.cursor()
cur.execute('select distinct customer.account, sequence, utilbill_id from reebill, customer, utilbill_reebill where customer_id = customer.id and reebill_id = reebill.id and version = 0 and issued != 1 order by account, sequence')
for account, sequence, utilbill_id in cur.fetchall():
    reebill = db.reebills.find_one({'_id.account': account, '_id.sequence': sequence, '_id.version': 0})

    for utilbill_subdoc in reebill['utilbills']:

        # find utility bill document attached to the reebill
        utilbill = db.utilbills.find_one({'_id': utilbill_subdoc['id']})
        if utilbill is None:
            print >> stderr, 'No utility bill document for reebill %s-%s-%s, id %s' % (reebill['_id']['account'], reebill['_id']['sequence'], reebill['_id']['version'], utilbill_subdoc['id'])
            continue

        # unissued version-0 reebills always have "sequence" and "version" keys in their utility bill. if not, something is wrong.
        try:
            assert 'sequence' in utilbill
            assert 'version' in utilbill
        except AssertionError:
            print >> stderr, 'unissued version-0 reebill lacks "sequence" and "version" in its utility bill:', reebill['_id']
            continue

        # find any existing editable utility bill documents with the same utility, service, and dates
        query_for_editable_twins = dict_merge(
                subdict(utilbill, ['account', 'utility', 'service', 'start', 'end']),
                {'sequence': {'$exists': False}})
        existing_editable_utility_bills = db.utilbills.find(query_for_editable_twins)

        # there should be at most 1 editable version of this utility bill
        if existing_editable_utility_bills.count() == 0:
            continue
        if existing_editable_utility_bills.count() > 1:
            print >> stderr, existing_editable_utility_bills.count(), 'editable utility bills match this query:', query_for_editable_twins
            continue

        # "un-freeze" the utility bill to which the reebill is attached
        del utilbill['sequence']
        del utilbill['version']

        # replace the existing editable utility bill with the previously frozen one, now editable
        db.utilbills.save(utilbill)
        db.utilbills.remove({'_id': existing_editable_utility_bills[0]['_id']}, True)

        # NOTE that a new document is not being created, so the document can
        # keep the same _id and the reebill subdocument "id" field does not
        # need to be updated

con.commit()
