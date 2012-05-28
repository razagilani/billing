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
from billing.dateutils import ISO_8601_DATE

sys.stdout = sys.stderr

# list of event types proposed but not used yet:
# ReeBillUsagePeriodUpdated
# ReeBillBillingPeriodUpdated
# ReeBillRateStructureModified
# PaymentEntered
# UtilBillDeleted
# TODO add utility bill uploaded? that has an account but no sequence

class JournalDAO(object):
    '''Performs queries for events in the journal.'''

    def __init__(self, host, port, database, collection):
        # global mongoengine connection object (not actually related to
        # JournalDAO itself)
        # TODO figure out how to use this the right way
        mongoengine.connect(database, host=host, port=int(port))

    def last_event_description(self, account):
        '''Returns a human-readable description of the last event for the given
        account. Returns an empty string if the account has no events.'''
        entries = list(JournalEntry.objects(account=account))
        if len(entries) == 0:
            return ''
        last_entry = entries[-1]
        return '%s on %s' % (str(last_entry),
                last_entry.date.strftime(ISO_8601_DATE))

    def load_entries(self, account):
        '''Returns a list of dictionaries describing all entries for the given
        account.'''
        result = []
        for event in JournalEntry.objects(account=account):
            d = event.to_dict()
            d.update({'event': event.description()})
            result.append(d)
        return result

class JournalEntry(mongoengine.Document):
    '''MongoEngine schema definition for all journal entries.
    
    This class should not be instantiated, and does not even have a constructor
    because MongoEngine makes a constructor for it, to which it passes the
    values of all the fields below as keyword arguments. That means you can't
    define a constructor whose arguments do not include all the field names.

    All descendants also have this problem, so they have save_instance() class
    methods which create an instance of the class and save it in Mongo.'''

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

    def __str__(self):
        '''Short human-readable description without date.'''
        return 'generic event--you should never see this!'

    def name(self):
        return 'generic event--you should never see this!'

    def description(self):
        '''Long human-readable description without date--same as __str__ by
        default.'''
        return str(self)

    def to_dict(self):
        '''Returns a JSON-ready dictionary representation of this journal
        entry.'''
        # TODO see if there's a way in MongoKit to get all the fields of a
        # mongoengine.Document. if so, to_dict() can be defined once here and
        # subclasses don't need to worry about it.
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

    def __str__(self):
        return 'Account %s created' % (self.account)

    def name(self):
        return 'Account Created'
    
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

    def __str__(self):
        return 'Note: %s' % (self.msg)

    def name(self):
        return 'Note'

    def to_dict(self):
        result = super(Note, self).to_dict()
        if hasattr(self, 'sequence'):
            result.update({'sequence': self.sequence})
        result.update({'msg': self.msg})
        return result

class UtilBillDeletedEvent(JournalEntry):
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
    
    def __str__(self):
        return '%s %s utility bill deleted' % (self.account, self.service)

    def description(self):
        return ('%s utility bill for service "%s" (from %s to %s) deleted, '
                'moved to %s') % (self.account, self.service,
                self.start_date, self.end_date, self.deleted_path)

    def name(self):
        return 'Utility bill deleted'

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

    def __str__(self):
        return 'Reebill %s-%s rolled' % (self.account, self.sequence)

    def name(self):
        return 'Reebill rolled'

class ReeBillBoundEvent(SequenceEvent):
    @classmethod
    def save_instance(cls, user, account, sequence):
        ReeBillBoundEvent(user=user.identifier, account=account,
                sequence=sequence).save()

    def __str__(self):
        return 'Reebill %s-%s bound to REE' % (self.account, self.sequence)

    def name(self):
        return 'Reebill bound to REE'

class ReeBillDeletedEvent(SequenceEvent):
    @classmethod
    def save_instance(cls, user, account, sequence):
        ReeBillDeletedEvent(user=user.identifier, account=account,
                sequence=sequence).save()

    def __str__(self):
        return 'Reebill %s-%s deleted' % (self.account, self.sequence)

    def name(self):
        return 'Reebill deleted' 

class ReeBillAttachedEvent(SequenceEvent):
    @classmethod
    def save_instance(cls, user, account, sequence):
        ReeBillAttachedEvent(user=user.identifier, account=account,
                sequence=sequence).save()

    def __str__(self):
        return 'Reebill %s-%s attached' % (self.account, self.sequence)

    def name(self):
        return 'Reebill attached to utility bills' 

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

    def __str__(self):
        return 'Reebill %s-%s mailed' % (self.account, self.sequence)

    def description(self):
        return 'Reebill %s-%s mailed to "%s"' % (self.account, self.sequence, self.address)

    def name(self):
        return 'Reebill mailed'

