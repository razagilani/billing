'''Removes "rates" from URS documents and moves any RSIs into the corresponding
UPRSs that are not already there.'''
from sys import stderr
import pymongo
from billing.util.dictutils import subdict, dict_merge

db = pymongo.Connection('localhost')['skyline-dev']

uprs_count = db.ratestructure.find({'_id.type': 'UPRS'}).count()
urs_count = db.ratestructure.find({'_id.type': 'URS'}).count()

for uprs in db.ratestructure.find({'_id.type': 'UPRS'}):
    # get URS corresponding to the UPRS
    query = {
        '_id.type': 'URS',
        '_id.utility_name': uprs['_id']['utility_name'],
        '_id.rate_structure_name': uprs['_id']['rate_structure_name']
    }
    urss = db.ratestructure.find(query)
    if urss.count() == 0:
        # if the URS is missing, it's not actually a problem; there's nothing to do
        print >> stderr, 'WARNING no URS found for query %s (nothing to update)' % query
        continue
    if urss.count() > 1:
        print >> stderr, 'ERROR more than one URS matches query %s' % query
        for u in urss:
            print >> stderr, '\t', urs['_id']
        continue

    urs = urss[0]

    # add to UPRS any RSIs in URS that are not in UPRS
    for urs_rsi in urs['rates']:
        if not any(uprs_rsi for uprs_rsi in uprs['rates'] if uprs_rsi['rsi_binding'] == urs_rsi['rsi_binding']):
            uprs['rates'].append(urs_rsi)

    db.ratestructure.save(uprs)

# remove "rates" from URS (register types still needed, maybe)
db.ratestructure.update({'_id.type': 'UPRS'}, {'$set': {'rates': []}})

try:
    assert db.ratestructure.find({'_id.type': 'UPRS'}).count() == uprs_count
    assert db.ratestructure.find({'_id.type': 'URS'}).count() == urs_count
except AssertionError:
    import ipdb; ipdb.set_trace()
