#!/usr/bin/python
import sys
import datetime
import uuid
import copy
import operator
import pymongo
import mongoengine
import ConfigParser
import os
from operator import attrgetter
from billing.util.dateutils import ISO_8601_DATE
from billing.processing.state import StateDB
from billing.processing.session_contextmanager import DBSession

# list of event types proposed but not used yet:
# ReeBillUsagePeriodUpdated
# ReeBillBillingPeriodUpdated
# ReeBillRateStructureModified
# PaymentEntered
# TODO add utility bill uploaded?

class JournalDAO(object):
    '''Performs queries for events in the journal.'''

    def last_event_summary(self, account):
        '''Returns a short human-readable description of the last event for the
        given account. Returns an empty string if the account has no events.'''
        entries = list(Event.objects(account=account))
        if len(entries) == 0:
            return ''
        last_entry = entries[-1]
        return '%s on %s' % (str(last_entry),
                last_entry.date.strftime(ISO_8601_DATE))

    def load_entries(self, account=None):
        '''Returns a list of dictionaries describing all entries for all
        accounts, or a specific account if 'account' is given.'''
        query = {'account': account} if account else {}
        result = [dict(e.to_dict(), event=e.description()) for e in
                Event.objects(**query)]
        return result

class Event(mongoengine.Document):
    '''MongoEngine schema definition for all events in the journal.
    
    This class should not be instantiated, and does not even have a constructor
    because MongoEngine makes a constructor for it, to which it passes the
    values of all the fields below as keyword arguments. That means you can't
    define a constructor whose arguments do not include all the field names.

    All descendants also have this problem, so they have save_instance() class
    methods which create an instance of the class and save it in Mongo.'''

    meta = {
        # all Event documents are associated with the database of the
        # MongoEngine connection whose "alias" is "journal", which should be
        # created by calling mongoengine.connect(alias='journal') in
        # BillToolBridge.__init__. if a class other than BTB wants to use the
        # journal, it must call mongoengine.connect(alias='journal') itself.
        'db_alias': 'journal',

        # collection name is hard-coded. i think there's no way to avoid that
        # unless the class is created dynamically.
        'collection': 'journal',

        'allow_inheritance': True
    }

    # fields in all journal entries and their types
    date = mongoengine.DateTimeField(required=True,
            default=datetime.datetime.utcnow)
    # eventually replace with ReferenceField to user document?
    user = mongoengine.StringField(required=False,
            # some old documents lack a "user" key
            default=None)
    account = mongoengine.StringField(required=True)

    def __str__(self):
        '''Short human-readable description without date.'''
        # Event can't be an abstract class because its metaclass is something
        # from MongoEngine, meaning it can't also have ABCMeta as its
        # metaclass. (every class's metaclass must be a subclass of its
        # superclass's metaclass.)
        raise NotImplementedError("Subclasses should override this.")

    def name(self):
        raise NotImplementedError("Subclasses should override this.")

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

###############################################################################
# account events

class AccountCreatedEvent(Event):
    meta = {'db_alias': 'journal'}
    @classmethod
    def save_instance(cls, user, account):
        AccountCreatedEvent(user=user.identifier, account=account).save()

    def __str__(self):
        return 'Account %s created' % (self.account)

    def name(self):
        return 'Account Created'

class Note(Event):
    meta = {'db_alias': 'journal'}
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

class UtilBillDeletedEvent(Event):
    meta = {'db_alias': 'journal'}
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
        result = ('%s utility bill for service "%s" from %s to %s deleted') % (
                self.account, self.service, self.start_date.date(),
                self.end_date.date())
        # not every deletion has a backup path (e.g. because there was never a
        # file or it could not be found when it was supposed to be deleted)
        if self.deleted_path is not None:
            result += ', backed up at %s' % self.deleted_path
        return result

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

###############################################################################
# reebill events

# TODO rename to ReeBillEvent (requires db upgrade because of MongoEngine
# "_cls" and "_types" keys)
class SequenceEvent(Event):
    meta = {'db_alias': 'journal'}
    '''Base class for events that are associated with a particular reebill. Do
    not instantiate.'''
    sequence = mongoengine.IntField(required=True)

    def to_dict(self):
        result = super(SequenceEvent, self).to_dict()
        result.update({'sequence': self.sequence})
        return result

class ReeBillRolledEvent(SequenceEvent):
    meta = {'db_alias': 'journal'}
    @classmethod
    def save_instance(cls, user, account, sequence):
        ReeBillRolledEvent(user=user.identifier, account=account,
                sequence=sequence).save()

    def __str__(self):
        return 'Reebill %s-%s rolled' % (self.account, self.sequence)

    def name(self):
        return 'Reebill rolled'

class ReeBillMailedEvent(SequenceEvent):
    meta = {'db_alias': 'journal'}
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
        return 'Reebill %s-%s mailed to "%s"' % (self.account, self.sequence,
                self.address)

    def name(self):
        return 'Reebill mailed'

###############################################################################
# specific-version events

class VersionEvent(SequenceEvent):
    meta = {'db_alias': 'journal'}
    '''Base class for events that are associated with a particular version of a
    reebill. Do not instantiate.'''
    version = mongoengine.IntField(required=True)

    def to_dict(self):
        result = super(VersionEvent, self).to_dict()
        result.update({'version': self.version})
        return result

class ReeBillBoundEvent(VersionEvent):
    meta = {'db_alias': 'journal'}
    @classmethod
    def save_instance(cls, user, account, sequence, version):
        ReeBillBoundEvent(user=user.identifier, account=account,
                sequence=sequence, version=version).save()

    def __str__(self):
        return 'Reebill %s-%s bound to REE' % (self.account, self.sequence)

    def name(self):
        return 'Reebill bound to REE'

class ReeBillDeletedEvent(VersionEvent):
    meta = {'db_alias': 'journal'}
    @classmethod
    def save_instance(cls, user, account, sequence, version):
        ReeBillDeletedEvent(user=user.identifier, account=account,
                sequence=sequence, version=version).save()

    def __str__(self):
        return 'Reebill %s-%s-%s deleted' % (self.account, self.sequence,
                self.version)

    def name(self):
        return 'Reebill deleted' 

class ReeBillAttachedEvent(VersionEvent):
    meta = {'db_alias': 'journal'}
    @classmethod
    def save_instance(cls, user, account, sequence, version):
        ReeBillAttachedEvent(user=user.identifier, account=account,
                sequence=sequence, version=version).save()

    def __str__(self):
        return 'Reebill %s-%s-%s attached to utility bills' % (self.account,
                self.sequence, self.version)

    def name(self):
        return 'Reebill attached' 

class ReeBillIssuedEvent(VersionEvent):
    '''Issuing of an actual version-0 reebill or a correction applied to later
    bill. For a correction, 'applied_sequence' (the sequence to which the
    adjustment was applied) should be given.'''
    meta = {'db_alias': 'journal'}
    applied_sequence = mongoengine.IntField(required=False)

    @classmethod
    def save_instance(cls, user, account, sequence, version,
            applied_sequence=None):
        if applied_sequence is None:
            # normal reebill
            assert version == 0
            ReeBillIssuedEvent(user=user.identifier, account=account,
                    sequence=sequence, version=version).save()
        else:
            # correction
            ReeBillIssuedEvent(user=user.identifier, account=account,
                    sequence=sequence, version=version,
                    applied_sequence=applied_sequence).save()

    def to_dict(self):
        result = super(ReeBillIssuedEvent, self).to_dict()
        if self.applied_sequence is not None:
            result.update({'applied_sequence': self.applied_sequence})
        return result

    def __str__(self):
        if self.applied_sequence is not None:
            return 'Correction %s-%s-%s issued with sequence %s' % (
                    self.account, self.sequence, self.version,
                    self.applied_sequence)
        else:
            return 'Reebill %s-%s-%s issued' % (self.account, self.sequence,
                    self.version)

    def name(self):
        return 'Reebill issued' 

class NewReebillVersionEvent(VersionEvent):
    meta = {'db_alias': 'journal'}
    
    @classmethod
    def save_instance(cls, user, account, sequence, version):
        NewReebillVersionEvent(user=user.identifier, account=account,
                sequence=sequence, version=version).save()

    def to_dict(self):
        result = super(NewReebillVersionEvent, self).to_dict()
        result.update({'version': self.version})
        return result

    def __str__(self):
        return 'Version %s of reebill %s-%s created' % (self.version,
                self.account, self.sequence)

    def name(self):
        return 'New version'

def main():
    config = ConfigParser.RawConfigParser()
    config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'reebill.cfg'))

    journal_config = dict(config.items('journaldb'))
    mongoengine.connect(journal_config['database'],
            host=journal_config['host'], port=int(journal_config['port']),
            alias='journal')
    dao = JournalDAO()

    #statedb_config = dict(config.items('statedb'))
    #state_db = StateDB(**statedb_config)

    #with DBSession(state_db) as session:
        #for account in state_db.listAccounts(session):
            #for entry in dao.load_entries(account):
                #print str(entry)

    for entry in sorted(Event.objects, key=attrgetter('date'), reverse=True):
        print '%s %10s    %s' % (entry.date.strftime('%Y-%m-%d %I:%M:%S %p'), entry.user, entry)

if __name__ == '__main__':
    main()
