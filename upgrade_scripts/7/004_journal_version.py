import pymongo
import mongoengine
from billing.reebill.journal import *

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

journaldb_config = {
    'host': 'localhost',
    'port': 27017,
    'database': 'skyline',
    'collection': 'journal',
}

connection = pymongo.Connection(journaldb_config['host'], journaldb_config['port'])
collection = connection[journaldb_config['database']]['journal']

# mappings from existing "event" values to Event subclasses
classes = [
    'ReeBillRolledEvent',
    'ReeBillBoundEvent',
    'ReeBillMailedEvent',
    'ReeBillDeletedEvent',
    'ReeBillAttachedEvent',
]

for entry in collection.find():
    cls = entry['_cls'].split('.')[-1]
    if cls in classes:
        print entry
        entry['version'] = 0
    collection.save(entry)
