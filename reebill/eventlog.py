#!/usr/bin/python
import pymongo
import datetime
from billing.mongo_utils import bson_convert
from billing.mongo_utils import python_convert

class EventLogger(object):

    def __init__(self, config):

        self.config = config
        self.connection = None
        self.database = None
        self.collection = None

        try:
            self.connection = pymongo.Connection(self.config['host'], int(self.config['port']))
        except Exception as e: 
            print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            raise e
        
        self.database = self.connection[self.config['database']]
        self.collection = self.database[self.config['collection']]


    def __del__(self):
        # TODO: 17928569 clean up mongo resources here?
        pass

    def log(self, event, **kwargs):
        '''Records an event in the log. **kwargs holds all other data to
        include with the event (e.g. account, sequence, branch for
        reebills).'''
        document = {
            'timestamp': datetime.utcnow(),
            'event': event, # event is actually a string, but consumers of this code should not need to know that
        }
        # stuff all the keyword arguments directly into mongo
        document.update(bson_convert(kwargs))
        self.collection.save(document)

    def load_entries(self, event, **kwargs):
        query = {
            'event': event
        }
        entries = self.collection.find(query)
        return map(python_convert, entries)

# enumeration of events:
# from https://www.pivotaltracker.com/story/show/23830853
# Outside this class, always refer to these as EventDao.ReeBillRolled, etc.
events_names = [
    'ReeBillRolled',
    'ReeBillBoundtoREE',
    'ReeBillUsagePeriodUpdated',
    'ReeBillBillingPeriodUpdated',
    'ReeBillRateStructureModified',
    'ReeBillCommitted'
]

# make each event in the 'event_names' dict a property of the class (with its
# own name as its value)
for event_name in event_names:
    setattr(EventLogger, event_name, event_name)
