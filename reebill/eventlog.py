#!/usr/bin/python
'''A machine-readable record of bill-processing events, e.g. for producing
reports about how long it takes to do various bill-processing tasks.'''
import pymongo
import datetime
from billing.mongo_utils import bson_convert
from billing.mongo_utils import python_convert

class EventLogger(object):

    def __init__(self, config):
        '''Initialize with a dictionary of key-value pairs from config file.'''
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
        '''Records an event in the log. Event must be one of the properties
        defined in 'event_names', e.g. EventLogger.ReeBillRolled. **kwargs holds
        all other data to include with the event (e.g. account, sequence,
        branch for reebills).'''
        if event not in event_names:
            raise ValueError('Unkown event: ' + str(event))

        document = {
            'timestamp': datetime.utcnow(),
            'event': event, # event is actually a string, but consumers of this code should not need to know that
        }
        # stuff all the keyword arguments directly into mongo
        document.update(bson_convert(kwargs))

        self.collection.save(document)

    def load_entries(self, event, **kwargs):
        '''Retrieve all events of type 'event', which must be one of the
        properties defined in 'event_names'.'''
        if event not in event_names:
            raise ValueError('Unkown event: ' + event)

        entries = self.collection.find({
            'event': event
        })
        return map(python_convert, entries)

# enumeration of events:
# from https://www.pivotaltracker.com/story/show/23830853 Outside this class,
# always refer to these as EventDao.ReeBillRolled, etc. because each event in
# the 'event_names' dict becomes a property of the EventLogger class (with its
# own name as its value)
event_names = set([ # using a set enforces uniqueness of entries
    'ReeBillRolled',
    'ReeBillBoundtoREE',
    'ReeBillUsagePeriodUpdated',
    'ReeBillBillingPeriodUpdated',
    'ReeBillRateStructureModified',
    'ReeBillCommitted'
])
for event_name in event_names:
    setattr(EventLogger, event_name, event_name)
