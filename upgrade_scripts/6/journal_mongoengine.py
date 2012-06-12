#!/usr/bin/python
'''Adds keys to all journal documents so they can be recognized by
MongoEngine.'''
import pymongo
from billing.reebill import journal

journaldb_config = {
    'host': 'localhost',
    'port': 27017,
    'database': 'skyline',
    'collection': 'journal',
}

connection = pymongo.Connection(journaldb_config['host'], journaldb_config['port'])
collection = connection[journaldb_config['database']]['journal']

for entry in collection.find():
    if '_types' not in entry:
        entry['_types'] = ['JournalEntry']
    if '_cls' not in entry:
        entry['_cls'] = 'JournalEntry'
    print entry
    collection.save(entry)
