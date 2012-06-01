import pymongo

db = 'skyline'

connection = pymongo.Connection('localhost')
collection = connection[db]['reebills']

fixed, total = 0, 0
bills = collection.find(sort=[('_id.account', pymongo.ASCENDING), ('_id.sequence', pymongo.ASCENDING)])
for bill in bills:
    if 'branch' in bill['_id']:
        del bill['_id']['branch']
        bill['_id']['version'] = 0
        collection.save(bill)
        print bill['_id'], 'fixed'
        fixed += 1
    else:
        print bill['_id'], 'skipped'
    total += 1
print '%s of %s bills fixed' % (fixed, total)
