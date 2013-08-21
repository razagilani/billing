'''Removes "rates" from URS documents and moves any RSIs into the corresponding
UPRSs that are not already there.'''
from sys import stderr
import pymongo
from billing.util.dictutils import subdict, dict_merge

db = pymongo.Connection('localhost')['skyline-dev']

for uprs in db.ratestructure.find({'_id.type': 'UPRS'}):
    # get URS corresponding to the UPRS
    db.ratestructure.find({
        '_id.type': 'URS',
        '_id.utility_name': uprs['_id']['utility_name']
        '_id.rate_structure_name': uprs['_id']['rate_structure_name']
    })

    # add to UPRS any RSIs in URS that are not in UPRS
    for urs_rsi in urs['rates']:
        if not any(uprs_rsi in uprs['rates'] if uprs_rsi['rsi_binding'] == urs_rsi['rsi_binding']):
            uprs['rates'].append(urs_rsi)

    db.ratestructure.save(uprs)

# remove "rates" from URS (register types still needed, maybe)
db.ratestructure.update({'_id.type': 'UPRS'}, {'$set': {'rates': []}})
