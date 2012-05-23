#!/usr/bin/python
import sys
import datetime
import uuid
import copy
import operator
import pymongo
import mongoengine
from billing.mongo_utils import bson_convert
from billing.mongo_utils import python_convert
from billing import dateutils

sys.stdout = sys.stderr

# list of events (keys) and their human-readable descriptions
# Outside this class, always refer to these as Journal.ReeBillRolled, etc.
event_names = {
    'Note': 'Note', # log event as a note
    'ReeBillRolled': 'Reebill rolled',
    'ReeBillBoundtoREE': 'RE&E offset bound', # TODO fix capitalization
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

class JournalEntry(mongoengine.Document):
    '''MongoEngine schema definition for journal entry document.'''

    # MongoEngine assumes the collection to use is the document class name
    # lowercased, but here we want to use the collection named "journal":
    meta = {'collection': 'journal'}
    # TODO create class dynamically to set collection name to the one passed
    # into JournalDAO constructor? i think python provides a way to do that...

    # all possible fields and their types
    date = mongoengine.DateTimeField(required=True)
    user = mongoengine.StringField(required=True) # eventually replace with ReferenceField to user document?
    event = mongoengine.StringField(choices=event_names.keys())
    account = mongoengine.StringField(required=True)
    sequence = mongoengine.IntField()
    msg = mongoengine.StringField() # only for Note events
    address = mongoengine.StringField() # only for ReeBillMailed events

    def to_dict(self):
        '''Returns a JSON-ready dictionary representation of this journal
        entry.'''
        # TODO see if there's a way in MongoKit to get all the fields instead
        # of explictly checking them all
        result = dict([
            ('date', self.date),
            ('user', self.user),
            ('event', self.event),
            ('account', self.account)
        ])
        if hasattr(self, 'sequence'):
            result.update({'sequence': self.sequence})
        if hasattr(self, 'msg'):
            result.update({'msg': self.msg})
        if hasattr(self, 'addresss'):
            result.update({'addresss': self.addresss})

        return result

class JournalDAO(object):
    '''Data Access Object for Journal Entries. Currently handles loading/saving
    of journal entry documents, but may disappear when we switch over
    completely to the MongoEngine way of doing things (documents save()
    themselves).'''

    def __init__(self, database, collection, host='localhost', port=27017):
        try:
            self.connection = mongoengine.connect(database, host=host,
                    port=int(port))
        except Exception as e: 
            print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            raise e

    def log_event(self, user, event_type, account, **kwargs):
        '''Logs an event associated with the given user and customer account
        (argument 'sequence' should be given to specify a particular reebill).
        A timestamp is produced automatically and the contents of kwargs will
        be inserted directly into the document.'''
        if event_type not in event_names:
            raise ValueError('Unknown event type: %s' % event_type)

        # create journal entry object with the required fields
        journal_entry = JournalEntry(user=user.identifier,
                date=datetime.datetime.utcnow(), event=event_type,
                account=account)

        # optional fields
        for kwarg, value in kwargs.iteritems():
            setattr(journal_entry, kwarg, value)

        # save in Mongo
        journal_entry.save()

    def load_entries(self, account):
        '''Returns a list of JSON-ready dictionaries of all journal entries for
        the given account.'''
        journal_entries = sorted(JournalEntry.objects(account=account),
                key=operator.attrgetter('date'))
        result = [entry.to_dict() for entry in journal_entries]
        return result

    def last_event_description(self, account):
        '''Returns a human-readable description of the last event for the given
        account. Returns an empty string if the account has no events.'''
        # TODO convert to MongoEngine style
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
            description = '%s on %s: %s' % (event_name,
                    last_entry['date'].strftime(dateutils.ISO_8601_DATE),
                    msg)
        else:
            description = '%s on %s' % (event_name,
                    last_entry['date'].strftime(dateutils.ISO_8601_DATE))
        return description


# make each key in the 'event_names' dict a property of the class (with its own
# name as its value)
for event_name in event_names.keys():
    setattr(JournalDAO, event_name, event_name)

if __name__ == '__main__':
    dao = JournalDAO(database='skyline', collection='journal')
    class FakeUser(object): pass
    user = FakeUser()
    setattr(user, 'identifier', 'dan')
    dao.log_event(user, JournalDAO.Note, '10003', msg="Does this note show up?!")
    entries = dao.load_entries('10003')
    print entries
