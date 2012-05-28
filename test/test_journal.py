import unittest
import pymongo
from datetime import date, datetime, timedelta
from billing.reebill import journal

class JournalTest(unittest.TestCase):

    def assertDatetimesClose(self, d1, d2):
        '''Asserts that datetimes d1 and d2 differ by less than 2 seconds.'''
        self.assertLess(abs(d1 - d2), timedelta(seconds=10))

    def assertDictMatch(self, d1, d2):
        '''Asserts that the two dictionaries are the same, up to str/unicode
        difference in strings and datetimes may only be close.'''
        self.assertEqual(sorted(d1.keys()), sorted(d2.keys()))
        for k, v in d1.iteritems():
            self.assertTrue(k in d2)
            v2 = d2[k]
            if type(v) is datetime and type(v2) is datetime:
                self.assertDatetimesClose(v, v2)
            else:
                self.assertEquals(v, v2)

    def setUp(self):
        self.database = 'test'
        self.collection = 'journal'

        # fake user object to create an event (just needs an
        # identifier)
        class FakeUser(object): pass
        user = FakeUser()
        setattr(user, 'identifier', 'dan')
        self.user = user

    def tearDown(self):
        # clear out database
        mongo_connection = pymongo.Connection()
        mongo_connection.drop_database(self.database)

    def test_account_created(self):
        journal.AccountCreatedEvent.save_instance(self.user, '99999')
        entries = journal.JournalEntry.objects
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
        entries = journal.JournalEntry.objects
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
        journal.UtilBillDeletedEvent.save_instance(self.user, '99999',
                date(2012,1,1), date(2012,2,1), 'gas',
                '/tmp/a_deleted_bill')
        entries = journal.JournalEntry.objects
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

    def test_reebill_mailed(self):
        journal.ReeBillMailedEvent.save_instance(self.user, '99999', 1,
                'jwatson@skylineinnovations.com')
        entries = journal.JournalEntry.objects
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

    def test_simple_sequence_events(self):
        '''Tests all the subclasses of SequenceEvent that don't have extra data
        besides user, account, and sequence.'''
        classes = [journal.ReeBillRolledEvent, journal.ReeBillBoundEvent,
                journal.ReeBillDeletedEvent, journal.ReeBillAttachedEvent]
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

    def test_load_entries(self):
        # 3 entries for 2 accounts
        journal.ReeBillRolledEvent.save_instance(self.user, 'account1', sequence=1)
        journal.Note.save_instance(self.user, 'account1', 'text of a note',
                sequence=2)
        journal.ReeBillBoundEvent.save_instance(self.user, 'account2',
                sequence=1)

        # load entries for account1
        dao = journal.JournalDAO()
        entries1 = dao.load_entries('account1')
        self.assertEquals(2, len(entries1))
        roll1, note1 = entries1
        self.assertEquals('Reebill rolled', roll1['event'])
        self.assertEquals('Note', note1['event'])

        # load entries for account2
        entries2 = dao.load_entries('account2')
        self.assertEquals(1, len(entries2))
        bound2 = entries2[0]
        self.assertEquals('Reebill bound to REE', bound2['event'])

if __name__ == '__main__':
    unittest.main(failfast=True)
