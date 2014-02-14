'''Replace "charge groups" with a list of charges, each having one "group".
'''
from itertools import chain
from pymongo import Connection
from billing.util.dictutils import dict_merge
db = Connection('localhost', 27017)['skyline-dev']

total_utilbills, total_reebills = db.utilbills.count(), db.reebills.count()

def convert(groups):
    return list(chain.from_iterable(
            (dict_merge(c, {'group': group_name}) for c in charges)
            for group_name, charges in groups.iteritems()))

# NOTE the condition in 'find' is necessary here because the cursor picks up
# new documents that were saved since the query was issued
for doc in db.utilbills.find({'chargegroups': {'$exists': True}}):
    doc['charges'] = convert(doc['chargegroups'])
    del doc['chargegroups']
    db.utilbills.save(doc)

for doc in db.reebills.find({'utilbills.hypothetical_chargegroups': {
        '$exists': True}}):
    for subdoc in doc['utilbills']:
        subdoc['hypothetical_charges'] = convert(subdoc[
                'hypothetical_chargegroups'])
        del subdoc['hypothetical_chargegroups']
    db.reebills.save(doc)

assert db.utilbills.find({'chargegroups': {'$exists': True}}).count() == 0
assert db.utilbills.find({'charges': {'$exists': False}}).count() == 0
assert db.reebills.find({'utilbills.hypothetical_chargegroups': {'$exists':
        True}}).count() == 0
assert db.reebills.find({'utilbills.hypothetical_charges': {'$exists':
        True}}).count() == total_reebills

