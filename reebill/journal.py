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

# list of event types proposed but not used yet:
# ReeBillUsagePeriodUpdated
# ReeBillBillingPeriodUpdated
# ReeBillRateStructureModified
# PaymentEntered
# UtilBillDeleted
# TODO add utility bill uploaded? that has an account but no sequence

# MongoEngine connection--TODO configure from config file
connection = mongoengine.connect('test')

class JournalDAO(object):
    def last_event_description(self, account):
        '''Returns a human-readable description of the last event for the given
        account. Returns an empty string if the account has no events.'''
        # TODO convert to MongoEngine style
        entries = JournalEntry.objects
        if len(entries) == 0:
            return ''
        last_entry = entries[-1]
        event_name = str(last_entry.__class__) # TODO human-readable event names
        description = '%s on %s' % (event_name,
                last_entry.date.strftime(dateutils.ISO_8601_DATE))
        return description

    def load_entries(self, account):
        '''Returns a list of dictionaries describing all entries for the given
        account.'''
        result = []
        for event in JournalEntry.objects(account=account):
            d = event.to_dict()
            d.update({'event': event.__class__.__name__})
            result.append(d)
        return result

class JournalEntry(mongoengine.Document):
    '''Base class containing MongoEngine schema definition for all journal
    entries. This class should not be instantiated, and does not even have a
    constructor because MongoEngine makes a constructor for it, to which it
    passes the values of all the fields. That means you can't define a
    constructor whose arguments do not include all the field names. All
    descendants of mongoengine.Document also have this problem, so they have
    save_instance() class methods which create an instance of the class and
    save it in Mongo.'''

    # MongoEngine assumes the collection to use is the document class name
    # lowercased, but here we want to use the collection named "journal":
    meta = {'collection': 'journal', 'allow_inheritance': True}
    # TODO create class dynamically to set collection name to the one passed
    # into JournalDAO constructor? i think python provides a way to do that...

    # all possible fields and their types
    date = mongoengine.DateTimeField(required=True,
            default=datetime.datetime.utcnow())
    user = mongoengine.StringField(required=True) # eventually replace with ReferenceField to user document?
    account = mongoengine.StringField(required=True)

    def to_dict(self):
        '''Returns a JSON-ready dictionary representation of this journal
        entry.'''
        # TODO see if there's a way in MongoKit to get all the fields instead
        # of explictly checking them all
        # https://www.pivotaltracker.com/story/show/30232105
        return dict([
            ('date', self.date),
            ('user', self.user),
            ('account', self.account)
        ])

class AccountCreatedEvent(JournalEntry):
    @classmethod
    def save_instance(cls, user, account):
        AccountCreatedEvent(user=user.identifier, account=account).save()
    
class Note(JournalEntry):
    '''JournalEntry subclass for Note events.'''
    event = 'Note'
    msg = mongoengine.StringField(required=True)

    # sequence is optional
    sequence = mongoengine.IntField()
    
    @classmethod
    def save_instance(cls, user, account, message, sequence=None):
        result = Note(user=user.identifier, account=account, msg=message)
        if sequence is not None:
            result.sequence = sequence
        result.save()

    def to_dict(self):
        result = super(Note, self).to_dict()
        if hasattr(self, 'sequence'):
            result.update({'sequence': self.sequence})
        result.update({'msg': self.msg})
        return result

class UtilBillDeletedEvent(JournalEntry):
    event = 'UtilBillDeleted'
    
    # mongo does not support date types and MongoEngine does not provide a
    # workaround. they will just be stored as datetimes
    start_date = mongoengine.DateTimeField()
    end_date = mongoengine.DateTimeField()
    service = mongoengine.StringField()
    deleted_path = mongoengine.StringField()

    @classmethod
    def save_instance(cls, user, account, start_date, end_date, service,
            deleted_path):
        UtilBillDeletedEvent(user=user.identifier, account=account,
                start_date=start_date, end_date=end_date, service=service,
                deleted_path=deleted_path).save()
    
    def to_dict(self):
        result = super(UtilBillDeletedEvent, self).to_dict()
        result.update({
            'start_date': self.start_date,
            'end_date': self.end_date,
            'service': self.service,
            'deleted_path': self.deleted_path
        })
        return result

class SequenceEvent(JournalEntry):
    '''Base class for events that are associated with a particular reebill. Do
    not instantiate.'''
    sequence = mongoengine.IntField(required=True)

    def to_dict(self):
        result = super(SequenceEvent, self).to_dict()
        result.update({'sequence': self.sequence})
        return result

class ReeBillRolledEvent(SequenceEvent):
    @classmethod
    def save_instance(cls, user, account, sequence):
        ReeBillRolledEvent(user=user.identifier, account=account,
                sequence=sequence).save()

class ReeBillBoundEvent(SequenceEvent):
    @classmethod
    def save_instance(cls, user, account, sequence):
        ReeBillBoundEvent(user=user.identifier, account=account,
                sequence=sequence).save()

class ReeBillDeletedEvent(SequenceEvent):
    @classmethod
    def save_instance(cls, user, account, sequence):
        ReeBillDeletedEvent(user=user.identifier, account=account,
                sequence=sequence).save()

class ReeBillAttachedEvent(SequenceEvent):
    @classmethod
    def save_instance(cls, user, account, sequence):
        ReeBillAttachedEvent(user=user.identifier, account=account,
                sequence=sequence).save()

class ReeBillMailedEvent(SequenceEvent):
    # email recipient(s)
    address = mongoengine.StringField()
    
    @classmethod
    def save_instance(cls, user, account, sequence, address):
        ReeBillMailedEvent(user=user.identifier, account=account,
                sequence=sequence, address=address).save()

    def to_dict(self):
        result = super(ReeBillMailedEvent, self).to_dict()
        result.update({'address': self.address})
        return result


if __name__ == '__main__':
    dao = JournalDAO(database='skyline', collection='journal')
    class FakeUser(object): pass
    user = FakeUser()
    setattr(user, 'identifier', 'dan')
    dao.log_event(user, JournalDAO.Note, '10003', msg="Does this note show up?!")
    entries = dao.load_entries('10003')
    print entries
