#!/usr/bin/python
import pymongo
from pymongo.objectid import ObjectId
from billing.reebill import journal

journaldb_config = {
    'host': 'localhost',
    'port': 27017,
    'database': 'skyline',
    'collection': 'reebills',
}

connection = pymongo.Connection(journaldb_config['host'], journaldb_config['port'])
collection = connection[journaldb_config['database']]['journal']

# convert every existing journal entry into an event of type "Note"
# (we don't care about putting old entries into the new categories, right?)
for entry in collection.find():
    entry['event'] = journal.JournalDAO.Note
    print dict(map(str, pair) for pair in entry.iteritems() if pair[0] != '_id')
    collection.save(entry)

# do we wnat to rename the collection? i think journal is still an ok name
#collection.rename('eventlog')
