#!/usr/bin/python
import pymongo
import datetime
import uuid
from billing.mongo_utils import bson_convert
from billing.mongo_utils import python_convert
from billing import dateutils
import sys
sys.stdout = sys.stderr

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

    ## TODO this should go away
    #def journal(self, account, sequence, message):
        #'''Special method that logs and event of type Note.'''
        #self.log_event(account, sequence, JournalDAO.Note, msg=message)

    def log_event(self, user, account, sequence, event_type, **kwargs):
        '''Logs an event associated with the given user and the reebill given
        by account and sequence. A timestamp is produced automatically and the
        contents of kwargs will be inserted directly into the document.'''
        if event_type not in event_names:
            raise ValueError('Unknown event type: %s' % event_type)
        journal_entry = {}
        for kwarg, value in kwargs.iteritems():
            journal_entry[kwarg] = value
        journal_entry['user'] = user.identifier
        journal_entry['account'] = account
        journal_entry['sequence'] = sequence
        journal_entry['date'] = datetime.datetime.utcnow()
        journal_entry['event'] = event_type
        # TODO include user identifier of the user who caused the event?

        journal_entry_data = bson_convert(journal_entry)

        self.collection.save(journal_entry_data)

    def load_entries(self, account):
        query = { "account": account }
        journal_entries = self.collection.find(query).sort('date')
        # TODO pagination
        return [python_convert(journal_entry) for journal_entry in journal_entries]

    def last_event_description(self, account):
        '''Returns a human-readable description of the last event for the given
        account. Returns an empty string if the account has no events.'''
        entries = self.load_entries(account)
        if entries == []:
            return ''
        last_entry = entries[-1]
        try:
            event_name = event_names[last_entry['event']]
        except KeyError:
            # TODO fix the data
            print >> sys.stderr, 'account %s has a journal entry with no "event" key: fix it!' % account
            event_name = '???'
        if event_name == JournalDAO.Note:
            try:
                msg = last_entry['msg']
            except KeyError:
                msg = ''
                print >> sys.stderr, 'journal entry of type "Note" has no "msg" key:', last_entry
            description = '%s on %s: %s' % (event_name, last_entry['date'].strftime(dateutils.ISO_8601_DATE), msg)
        else:
            description = '%s on %s' % (event_name, last_entry['date'].strftime(dateutils.ISO_8601_DATE))
        return description


# list of events (keys) and their human-readable descriptions
# Outside this class, always refer to these as Journal.ReeBillRolled, etc.
event_names = {
    'Note': 'Note', # log event as a note
    'ReeBillRolled': 'Reebill rolled',
    'ReeBillBoundtoREE': 'RE&E offset bound',
    'ReeBillUsagePeriodUpdated': 'Usage period updated',
    'ReeBillBillingPeriodUpdated': 'Billing period updated',
    'ReeBillRateStructureModified': 'Rate structure modified',
    'ReeBillCommitted': 'Reebill committed', # TODO delete? has this ever been used?
    'ReeBillMailed': 'Utility bills attached to reebill',
    'ReeBillDeleted': 'Reebill deleted',
    'ReeBillAttached': 'Reebill attached to utility bills',
    'PaymentEntered': 'Payment entered',
    'AccountCreated': 'Account created', # no sequence associated with this one
}
# make each key in the 'event_names' dict a property of the class (with its own
# name as its value)
for event_name in event_names.keys():
    setattr(JournalDAO, event_name, event_name)
