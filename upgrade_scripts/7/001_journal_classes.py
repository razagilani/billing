#!/usr/bin/python
'''Sets _cls and _types fields for journal entry documents so MongoEngine knows
what class they are.'''
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

def full_class_name(cls):
    '''Path down the family tree from Event to cls with names separated by "."'''
    result = cls.__name__
    if cls != Event:
        if len(cls.__bases__) != 1:
            raise Exception
        result = full_class_name(cls.__bases__[0]) + '.' + result
    return result

def all_ancestors(cls):
    '''List of all ancestors of cls, including cls itself, in same format as
    above.'''
    result = [full_class_name(cls)]
    while cls != Event:
        if len(cls.__bases__) != 1:
            raise Exception
        cls = cls.__bases__[0]
        result.append(full_class_name(cls))
    return result

# mappings from existing "event" values to Event subclasses
classes = {
    'Note': Note,
    'ReeBillRolled': ReeBillRolledEvent,
    'ReeBillBoundtoREE': ReeBillBoundEvent,
    'ReeBillMailed': ReeBillMailedEvent,
    'ReeBillDeleted': ReeBillDeletedEvent,
    'ReeBillAttached': ReeBillAttachedEvent,
    'AccountCreated': AccountCreatedEvent,
}

for entry in collection.find():
    if 'event' not in entry:
        print '************ entry lacks "event" key:'
        pp(entry)
        continue
    cls = classes[entry['event']]
    entry['_cls'] = full_class_name(cls)
    entry['_types'] = all_ancestors(cls)
    del entry['event']
    collection.save(entry)
