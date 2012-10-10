import unittest
import pymongo
import mongoengine
from datetime import date, datetime, timedelta
from time import sleep
from billing.reebill import journal
from billing.dateutils import ISO_8601_DATE
from billing.test import utils

class JournalTest(utils.TestCase):

    # TODO test __str__ methods and descriptions of all event types

    def setUp(self):
        self.database = 'test'

        result = mongoengine.connect(self.database, alias='journal')

        # fake user object to create an event (just needs an
        # identifier)
        class FakeUser(object): pass
        user = FakeUser()
        setattr(user, 'identifier', 'dan')
        self.user = user

        self.dao = journal.JournalDAO()

    def tearDown(self):
        # clear out database
        mongo_connection = pymongo.Connection()
        mongo_connection.drop_database(self.database)

    def test_account_created(self):
        journal.AccountCreatedEvent.save_instance(self.user, '99999')
        entries = journal.Event.objects
        self.assertEquals(1, len(entries))
        entry = entries[0]
        self.assertTrue(isinstance(entry, journal.AccountCreatedEvent))
        self.assertDatetimesClose(datetime.utcnow(), entry.date)
        self.assertEquals(self.user.identifier, entry.user)
        self.assertEquals('99999', entry.account)
        self.assertDictMatch({
            'user': 'dan',
            'account': '99999',
            'date': datetime.utcnow(),
            }, entry.to_dict())

    def test_note(self):
        journal.Note.save_instance(self.user, '99999', 'hello',
                sequence=1)
        entries = journal.Event.objects
        self.assertEquals(1, len(entries))
        entry = entries[0]
        self.assertDatetimesClose(datetime.utcnow(), entry.date)
        self.assertEquals(self.user.identifier, entry.user)
        self.assertTrue(isinstance(entry, journal.Note))
        self.assertEquals('99999', entry.account)
        self.assertEquals(1, entry.sequence)
        self.assertEquals('hello', entry.msg)
        self.assertDictMatch({
            'user': 'dan',
            'account': '99999',
            'msg': 'hello',
            'sequence': 1,
            'date': datetime.utcnow(),
            }, entry.to_dict())
    
    def test_utilbill_deleted(self):
        # with a backup path
        journal.UtilBillDeletedEvent.save_instance(self.user, '99999',
                date(2012,1,1), date(2012,2,1), 'gas',
                '/tmp/a_deleted_bill')
        entries = journal.Event.objects
        self.assertEquals(1, len(entries))
        entry = entries[0]
        self.assertDatetimesClose(datetime.utcnow(), entry.date)
        self.assertEquals(self.user.identifier, entry.user)
        self.assertTrue(isinstance(entry, journal.UtilBillDeletedEvent))
        self.assertEquals('99999', entry.account)
        self.assertEquals(datetime(2012,1,1), entry.start_date)
        self.assertEquals(datetime(2012,2,1), entry.end_date)
        self.assertEquals('gas', entry.service)
        self.assertEquals('/tmp/a_deleted_bill', entry.deleted_path)
        self.assertDictMatch({
            'user': 'dan',
            'account': '99999',
            'service': 'gas',
            'start_date': datetime(2012,1,1),
            'end_date': datetime(2012,2,1),
            'deleted_path': '/tmp/a_deleted_bill',
            'date': datetime.utcnow()
            }, entry.to_dict())

        # without
        journal.UtilBillDeletedEvent.save_instance(self.user, '99999',
                date(2012,1,1), date(2012,2,1), 'gas', None)
        entries = journal.Event.objects
        self.assertEquals(2, len(entries))
        entry = entries[1]
        self.assertDatetimesClose(datetime.utcnow(), entry.date)
        self.assertEquals(self.user.identifier, entry.user)
        self.assertTrue(isinstance(entry, journal.UtilBillDeletedEvent))
        self.assertEquals('99999', entry.account)
        self.assertEquals(datetime(2012,1,1), entry.start_date)
        self.assertEquals(datetime(2012,2,1), entry.end_date)
        self.assertEquals('gas', entry.service)
        self.assertEquals(None, entry.deleted_path)
        self.assertDictMatch({
            'user': 'dan',
            'account': '99999',
            'service': 'gas',
            'start_date': datetime(2012,1,1),
            'end_date': datetime(2012,2,1),
            'deleted_path': None,
            'date': datetime.utcnow()
            }, entry.to_dict())

    def test_reebill_mailed(self):
        journal.ReeBillMailedEvent.save_instance(self.user, '99999', 1,
                'jwatson@skylineinnovations.com')
        entries = journal.Event.objects
        self.assertEquals(1, len(entries))
        entry = entries[0]
        self.assertDatetimesClose(datetime.utcnow(), entry.date)
        self.assertEquals(self.user.identifier, entry.user)
        self.assertTrue(isinstance(entry, journal.ReeBillMailedEvent))
        self.assertEquals('99999', entry.account)
        self.assertEquals(1, entry.sequence)
        self.assertEquals('jwatson@skylineinnovations.com', entry.address)
        self.assertDictMatch({
            'user': 'dan',
            'account': '99999',
            'sequence': 1,
            'address': 'jwatson@skylineinnovations.com',
            'date': datetime.utcnow()
            }, entry.to_dict())

    def test_new_version(self):
        journal.NewReebillVersionEvent.save_instance(self.user, '99999', 1, 23)
        entries = journal.Event.objects
        self.assertEquals(1, len(entries))
        entry = entries[0]
        self.assertTrue(isinstance(entry, journal.NewReebillVersionEvent))
        self.assertDatetimesClose(datetime.utcnow(), entry.date)
        self.assertEquals(self.user.identifier, entry.user)
        self.assertEquals('99999', entry.account)
        self.assertEquals(1, entry.sequence)
        self.assertEquals(23, entry.version)
        self.assertDictMatch({
            'user': 'dan',
            'account': '99999',
            'sequence': 1,
            'version': 23,
            'date': datetime.utcnow(),
            }, entry.to_dict())

    def test_reebill_issued(self):
        # normal reebill
        journal.ReeBillIssuedEvent.save_instance(self.user, '99999', 1, 0)
        entries = journal.Event.objects
        self.assertEquals(1, len(entries))
        entry = entries[0]
        self.assertTrue(isinstance(entry, journal.ReeBillIssuedEvent))
        self.assertDatetimesClose(datetime.utcnow(), entry.date)
        self.assertEquals(self.user.identifier, entry.user)
        self.assertEquals('99999', entry.account)
        self.assertEquals(1, entry.sequence)
        self.assertEquals(0, entry.version)
        self.assertDictMatch({
            'user': 'dan',
            'account': '99999',
            'sequence': 1,
            'version': 0,
            'date': datetime.utcnow(),
            }, entry.to_dict())

        # correction 2 on sequence 3 issued with sequence 5
        journal.ReeBillIssuedEvent.save_instance(self.user, '99999', 3, 2,
                applied_sequence=5)
        entries = journal.Event.objects
        self.assertEquals(2, len(entries))
        entry = entries[1]
        self.assertEquals(5, entry.applied_sequence)
        self.assertDictMatch({
            'user': 'dan',
            'account': '99999',
            'sequence': 3,
            'version': 2,
            'applied_sequence': 5,
            'date': datetime.utcnow(),
            }, entry.to_dict())

    def test_simple_sequence_events(self):
        '''Tests all the subclasses of SequenceEvent that don't have extra data
        besides user, account, and sequence.'''
        classes = [journal.ReeBillRolledEvent]
        for cls in classes:
            cls.save_instance(self.user, '99999', 1)
            entries = cls.objects
            self.assertEquals(1, len(entries))
            entry = entries[0]
            self.assertDatetimesClose(datetime.utcnow(), entry.date)
            self.assertEquals(self.user.identifier, entry.user)
            self.assertTrue(isinstance(entry, cls))
            self.assertEquals('99999', entry.account)
            self.assertEquals(1, entry.sequence)
            self.assertDictMatch({
                'user': 'dan',
                'account': '99999',
                'sequence': 1,
                'date': datetime.utcnow()
                }, entry.to_dict())

    def test_simple_version_events(self):
        '''Tests all the subclasses of VersionEvent that don't have extra data
        besides user, account, sequence, and version.'''
        classes = [journal.ReeBillBoundEvent, journal.ReeBillDeletedEvent,
                journal.ReeBillAttachedEvent]
        for cls in classes:
            cls.save_instance(self.user, '99999', 1, 0)
            entries = cls.objects
            self.assertEquals(1, len(entries))
            entry = entries[0]
            self.assertDatetimesClose(datetime.utcnow(), entry.date)
            self.assertEquals(self.user.identifier, entry.user)
            self.assertTrue(isinstance(entry, cls))
            self.assertEquals('99999', entry.account)
            self.assertEquals(1, entry.sequence)
            self.assertDictMatch({
                'user': 'dan',
                'account': '99999',
                'sequence': 1,
                'version': 0,
                'date': datetime.utcnow()
                }, entry.to_dict())

    def test_load_entries(self):
        # 3 entries for 2 accounts
        journal.ReeBillRolledEvent.save_instance(self.user, '90001', sequence=1)
        journal.Note.save_instance(self.user, '90001', 'text of a note',
                sequence=2)
        journal.ReeBillBoundEvent.save_instance(self.user, '90002', 1, 0)

        # load entries for 99999
        entries1 = self.dao.load_entries('90001')
        self.assertEquals(2, len(entries1))
        roll1, note1 = entries1
        self.assertEquals('Reebill 90001-1 rolled', roll1['event'])
        self.assertEquals('Note: text of a note', note1['event'])

        # load entries for account2
        entries2 = self.dao.load_entries('90002')
        self.assertEquals(1, len(entries2))
        bound2 = entries2[0]
        self.assertEquals('Reebill 90002-1 bound to REE', bound2['event'])

    def test_last_event_summary(self):
        journal.Note.save_instance(self.user, '90001', 'text of a note',
                sequence=2)
        journal.ReeBillRolledEvent.save_instance(self.user, '90001', 1)
        journal.ReeBillBoundEvent.save_instance(self.user, '90002', 1, 0)
        description = self.dao.last_event_summary('90001')
        self.assertEqual('Reebill 90001-1 rolled on ' + datetime.utcnow().date()
                .strftime(ISO_8601_DATE), description)
        
    def test_dates(self):
        '''Catches a bug where successive events have the same date:
        https://www.pivotaltracker.com/story/show/32141609.'''
        # 2 notes created about 5 seconds apart
        journal.Note.save_instance(self.user, '90001', 'first event')
        sleep(5)
        journal.Note.save_instance(self.user, '90001', '5 seconds later')
        events = journal.Event.objects
        assert len(events) == 2

        # their dates should be about 5 seconds apart
        # (assertDatetimesClose is not very precise, but the test will fail if
        # they have have the exact same date)
        self.assertDatetimesClose(events[0].date + timedelta(seconds=5),
                events[1].date, seconds=1)

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
