#!/usr/bin/python
import pymongo
import mongoengine
from billing.reebill.journal import *

db = 'skyline'

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

# use pymongo to fix class names
col = pymongo.Connection('localhost')[db]['journal']
count = 0
for entry in col.find():
    classes = entry['_cls'].split('.')
    actual_class_name = classes[-1]
    if actual_class_name in ['ReeBillBoundEvent', 'ReeBillDeletedEvent', 'ReeBillAttachedEvent', 'NewReebillVersionEvent']:
        actual_class = eval(actual_class_name)
        entry['_cls'] = full_class_name(actual_class)
        entry['_types'] = all_ancestors(actual_class)
        col.save(entry)
        count += 1
print 'fixed class name in %s entries' % count


# set version to 0
mongoengine.connect(db, alias='journal')
fixed, skipped = 0, 0
for entry in VersionEvent.objects:
    entry.version = 0
    try:
        entry.save()
        fixed += 1
    except ValidationError as e:
        print 'skipped due to ValidationError:', entry
        skipped += 1 
print 'put version 0 in %s entries' % fixed
print skipped, 'errors'
