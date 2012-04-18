#!/usr/bin/python
import sys
import datetime
import uuid
import copy
import pymongo
import mongokit
from mongokit import OR, IS
from billing.mongo_utils import bson_convert
from billing.mongo_utils import python_convert
from billing import dateutils

sys.stdout = sys.stderr

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

    # TODO add utility bill uploaded? that has an account but no sequence
}

class JournalEntry(mongokit.Document):
    '''MongoKit schema definition for journal entry document.'''
    # In normal MongoKit usage one defines __database__ and __collection__
    # properties here. But we want to configure the databse and collection
    # dynamically, so we "register" this class with the database collection
    # object in the JournalDAO constructor, which makes this class a property
    # of JournalDAO's 'collection'; we use collection.JournalEntry instead of
    # just JournalEntry to create journal entries that belong to that
    # collection.

    # all possible fields and their types
    structure = {
        # the required fields
        'date': datetime.datetime,
        'user': basestring, # user identifier (not username)
        'event': IS(*event_names), # one of the event names defined above
        'account': basestring,
        'sequence': int,

        # only for Note events
        'msg': basestring,

        # only for ReeBillMailed events
        'address': basestring,
        #...
    }

    # subset of the above fields that are required in every document
    # TODO sequence should not be required for AccountCreated event
    required_fields = ['date', 'user', 'event', 'account', 'sequence']

    # allow non-unicode string types that mongokit forbids by default (for some
    # reason 'str' must be included to allow str values in basestring
    # variables, even though all strs are basestrings)
    authorized_types = mongokit.Document.authorized_types + [str, basestring] 

    # prevent MongoKit from inserting None for all non-required fields when
    # they're not given?
    use_schemaless = True
    # (does not work)


class JournalDAO(object):

    def __init__(self, database, collection, host='localhost', port=27017):
        try:
            # mongokit Connection is subclass of pymongo Connection
            self.connection = mongokit.Connection(host, int(port))
        except Exception as e: 
            print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            raise e

        # mongokit requires some kind of association between the JournalEntry
        # class and the database Connection. this makes the JournalEntry class
        # a property of the Connection object.
        self.connection.register(JournalEntry)
        
        self.database = self.connection[database]
        self.collection = self.database[collection]

    def __del__(self):
        # TODO: 17928569 clean up mongo resources here?
        pass

    def log_event(self, user, account, sequence, event_type, **kwargs):
        '''Logs an event associated with the given user and the reebill given
        by account and sequence. A timestamp is produced automatically and the
        contents of kwargs will be inserted directly into the document.'''
        if event_type not in event_names:
            raise ValueError('Unknown event type: %s' % event_type)

        # create empty JournalEntry object: you must use
        # collection.JournalEntry and not just JournalEntry, because the latter
        # doesn't know what class it's supposed to be associated with
        journal_entry = self.collection.JournalEntry()

        for kwarg, value in kwargs.iteritems():
            journal_entry[kwarg] = value

        # required fields
        journal_entry['user'] = user.identifier
        journal_entry['date'] = datetime.datetime.utcnow()
        journal_entry['event'] = event_type
        journal_entry['account'] = account
        journal_entry['sequence'] = sequence

        #journal_entry_data = bson_convert(journal_entry)
        #self.collection.save(journal_entry_data)
        journal_entry.save()

    def load_entries(self, account):
        # TODO pagination
        query = { "account": account }
        journal_entries = self.collection.find(query).sort('date')
        # copy each entry to prevent outside code from modifying the real
        # database document
        # TODO remove python_convert?
        return [copy.deepcopy(python_convert(journal_entry)) for journal_entry
                in journal_entries]

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


# make each key in the 'event_names' dict a property of the class (with its own
# name as its value)
for event_name in event_names.keys():
    setattr(JournalDAO, event_name, event_name)

if __name__ == '__main__':
    dao = JournalDAO(database='skyline', collection='journal')
    entries = dao.load_entries('10003')

    class FakeUser(object): pass
    fakeuser = FakeUser()
    setattr(fakeuser, 'identifier', 'fake')

    import pdb; pdb.set_trace()
    dao.log_event(fakeuser, '99999', 1, 'Note', msg='hello')
