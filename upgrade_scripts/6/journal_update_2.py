#!/usr/bin/python
import pymongo
from pymongo.objectid import ObjectId
from billing.reebill import journal

journaldb_config = {
    'host': 'localhost',
    'port': 27017,
    'database': 'skyline',
    'collection': 'journal',
}

connection = pymongo.Connection(journaldb_config['host'], journaldb_config['port'])
collection = connection[journaldb_config['database']]['journal']

# convert every existing journal entry that lacks an event type into an event
# of type "Note"
for entry in collection.find():
    if 'event' not in entry:
        entry['event'] = journal.JournalDAO.Note
        collection.save(entry)
    print dict(map(str, pair) for pair in entry.iteritems() if pair[0] != '_id')
    if entry['event'] == journal.JournalDAO.Note == 'msg' not in entry:
        print '    entry lacks key "msg"'

# do we wnat to rename the collection? i think journal is still an ok name
#collection.rename('eventlog')
