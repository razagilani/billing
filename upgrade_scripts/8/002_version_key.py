#!/usr/bin/python
import pymongo

db = 'skyline'

connection = pymongo.Connection('localhost')
reebills_collection = connection[db]['reebills']
rs_collection = connection[db]['ratestructure']

# reebills
bills = reebills_collection.find(sort=[('_id.account', pymongo.ASCENDING), ('_id.sequence', pymongo.ASCENDING)])
bills_fixed, bills_total = 0, 0
for bill in bills:
    if 'branch' in bill['_id']:
        # remove old doc
        reebills_collection.remove({'_id': bill['_id']})
        # fix it and save
        del bill['_id']['branch']
        bill['_id']['version'] = 0
        reebills_collection.save(bill)
        print 'reebill', bill['_id'], 'fixed'
        bills_fixed += 1
    else:
        print 'reebill', bill['_id'], 'skipped'
    bills_total += 1

# customer periodic rate structures
cprss = rs_collection.find({'_id.type': 'CPRS'}, sort=[('_id.account', pymongo.ASCENDING), ('_id.sequence', pymongo.ASCENDING)])
rs_fixed, rs_total = 0, 0
for cprs in cprss:
    if 'branch' in cprs['_id']:
        # remove old doc
        rs_collection.remove({'_id': cprs['_id']})
        # fix it and save
        del cprs['_id']['branch']
        cprs['_id']['version'] = 0
        rs_collection.save(cprs)
        print 'CPRS', cprs['_id'], 'fixed'
        rs_fixed += 1
    else:
        print 'CPRS', cprs['_id'], 'skipped'
    rs_total += 1

print '%s of %s reebills fixed' % (bills_fixed, bills_total)
print '%s of %s CPRSs fixed' % (rs_fixed, rs_total)
