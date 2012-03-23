#!/usr/bin/python
import pymongo
import datetime
import uuid
from billing.mongo_utils import bson_convert
from billing.mongo_utils import python_convert

class JournalDAO(object):

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

    def journal(self, account, sequence, message):
        '''Special method that logs and event of type Note.'''
        self.log_event(account, sequence, JournalDAO.Note, msg=message)

    def log_event(self, account, sequence, event_type, **kwargs):
        '''Logs an event associated with the reebill given by account and
        sequence. A timestamp is produced automatically and the contents of
        kwargs will be inserted directly into the document.'''
        if event_type not in event_names:
            raise ValueError('Unknown event type: %s' % event_type)
        journal_entry = {}
        for kwarg, value in kwargs.iteritems():
            journal_entry[kwarg] = value
        journal_entry['account'] = account
        journal_entry['sequence'] = int(sequence)
        journal_entry['date'] = datetime.datetime.utcnow()
        journal_entry['event'] = event_type
        # TODO include user identifier of the user who caused the event?

        journal_entry_data = bson_convert(journal_entry)

        self.collection.save(journal_entry_data)

    def load_entries(self, account):
        query = { "account": account }
        journal_entries = self.collection.find(query)
        # TODO pagination
        return [python_convert(journal_entry) for journal_entry in journal_entries]


# enumeration of events:
# from https://www.pivotaltracker.com/story/show/23830853
# Outside this class, always refer to these as Journal.ReeBillRolled, etc.
event_names = [
    'Note', # log event as a note
    'ReeBillRolled',
    'ReeBillBoundtoREE',
    'ReeBillUsagePeriodUpdated',
    'ReeBillBillingPeriodUpdated',
    'ReeBillRateStructureModified',
    'ReeBillCommitted', # TODO change name
    'ReeBillMailed',
    'ReeBillDeleted',
    # possible others
    'PaymentEntered',
    'AccountCreated', # no sequence associated with this one
]
# make each event in the 'event_names' dict a property of the class (with its
# own name as its value)
for event_name in event_names:
    setattr(JournalDAO, event_name, event_name)
