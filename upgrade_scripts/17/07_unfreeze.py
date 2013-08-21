from sys import stderr
import pymongo
from billing.util.dateutils import date_to_datetime
from bson import ObjectId
from billing.util.dictutils import subdict, dict_merge

db = pymongo.Connection('localhost')['skyline-dev']

# iterate through all unissued version-0 reebill documents
for reebill in db.reebills.find({'_id.version': 0, 'issue_date': None}):

    for utilbill_subdoc in reebill['utilbills']:
        utilbill = db.utilbills.find_one({'_id': utilbill_subdoc['id']})
        if utilbill is None:
            print >> stderr, 'No utility bill for reebill %s-%s-%s, id %s' % (reebill['_id']['account'], reebill['_id']['sequence'], reebill['_id']['version'], utilbill_subdoc['id'])
            continue

        # unissued version-0 reebills always have "sequence" and "version" keys in their utility bill. if not, something is wrong.
        try:
            assert 'sequence' in utilbill
            assert 'version' in utilbill
        except AssertionError:
            print >> stderr, 'unissued version-0 reebill lacks "sequence" and "version" in its utility bill:', reebill['_id']
            continue

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

